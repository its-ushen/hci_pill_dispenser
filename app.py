from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import json

app = Flask(__name__)
# Change this to a secure secret key
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pill_dispenser.db'
db = SQLAlchemy(app)

# Store active SSE connections
active_connections = set()

# Database Models


class Funnel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    medication = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    is_configured = db.Column(db.Boolean, default=False)


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    prescriptions = db.relationship(
        'Prescription', backref='patient', lazy=True)
    dispense_history = db.relationship(
        'DispenseHistory', backref='patient', lazy=True)


# Association table for prescription-funnel many-to-many relationship
prescription_funnels = db.Table('prescription_funnels',
                                db.Column('prescription_id', db.Integer, db.ForeignKey(
                                    'prescription.id'), primary_key=True),
                                db.Column('funnel_id', db.Integer, db.ForeignKey(
                                    'funnel.id'), primary_key=True)
                                )


class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey(
        'patient.id'), nullable=False)
    dosage = db.Column(db.Integer, nullable=False)  # pills per funnel
    start_date = db.Column(db.DateTime, nullable=False,
                           default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=True)
    # Many-to-many relationship with funnels
    funnels = db.relationship('Funnel', secondary=prescription_funnels, lazy='subquery',
                              backref=db.backref('prescriptions', lazy=True))


class DispenseHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey(
        'patient.id'), nullable=False)
    prescription_id = db.Column(db.Integer, db.ForeignKey(
        'prescription.id'), nullable=False)
    funnel_id = db.Column(db.Integer, db.ForeignKey(
        'funnel.id'), nullable=False)
    medication = db.Column(db.String(100), nullable=False)
    pills_dispensed = db.Column(db.Integer, nullable=False)
    dispense_time = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow)


def create_default_funnels():
    # Check if funnels exist
    if not Funnel.query.first():
        # Create three default funnels
        funnels = [
            Funnel(name="Funnel 1", medication="",
                   capacity=0, is_configured=False),
            Funnel(name="Funnel 2", medication="",
                   capacity=0, is_configured=False),
            Funnel(name="Funnel 3", medication="",
                   capacity=0, is_configured=False)
        ]
        for funnel in funnels:
            db.session.add(funnel)
        db.session.commit()


def send_dispense_event(data):
    """Send dispense event to all connected clients"""
    event_data = f"data: {json.dumps(data)}\n\n"
    dead_connections = set()
    for connection in active_connections:
        try:
            connection.write(event_data)
        except:
            dead_connections.add(connection)
    # Remove any dead connections
    active_connections.difference_update(dead_connections)

# Routes


@app.route('/')
def index():
    funnels = Funnel.query.all()
    patients = Patient.query.all()
    return render_template('index.html', funnels=funnels, patients=patients)


@app.route('/funnel/configure/<int:funnel_id>', methods=['GET', 'POST'])
def configure_funnel(funnel_id):
    funnel = Funnel.query.get_or_404(funnel_id)

    if request.method == 'POST':
        funnel.medication = request.form['medication']
        funnel.capacity = int(request.form['capacity'])
        funnel.is_configured = True
        db.session.commit()
        flash('Funnel configured successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('configure_funnel.html', funnel=funnel)


@app.route('/patient/add', methods=['GET', 'POST'])
def add_patient():
    if request.method == 'POST':
        name = request.form['name']
        patient = Patient(name=name)
        db.session.add(patient)
        db.session.commit()
        flash('Patient added successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('add_patient.html')


@app.route('/prescription/add', methods=['GET', 'POST'])
def add_prescription():
    if request.method == 'POST':
        patient_id = int(request.form['patient_id'])
        # Get multiple funnel selections
        funnel_ids = request.form.getlist('funnel_ids')
        dosage = int(request.form['dosage'])

        # Create new prescription
        prescription = Prescription(
            patient_id=patient_id,
            dosage=dosage
        )

        # Add selected funnels to prescription
        for funnel_id in funnel_ids:
            funnel = Funnel.query.get(int(funnel_id))
            if funnel and funnel.is_configured:
                prescription.funnels.append(funnel)

        db.session.add(prescription)
        db.session.commit()
        flash('Prescription added successfully!', 'success')
        return redirect(url_for('index'))

    patients = Patient.query.all()
    funnels = Funnel.query.filter_by(is_configured=True).all()
    return render_template('add_prescription.html', patients=patients, funnels=funnels)


@app.route('/prescription/dispense/<int:prescription_id>')
def dispense_prescription(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    patient = prescription.patient

    # Create JSON format for the IoT device
    dispense_data = {
        "prescription_id": prescription.id,
        "patient_name": patient.name,
        "timestamp": datetime.utcnow().isoformat(),
        "medications": [
            {
                "funnel_id": funnel.id,
                "funnel_name": funnel.name,
                "medication": funnel.medication,
                "pills": prescription.dosage
            }
            for funnel in prescription.funnels
        ]
    }

    # Log dispense history for each medication
    for funnel in prescription.funnels:
        history = DispenseHistory(
            patient_id=patient.id,
            prescription_id=prescription.id,
            funnel_id=funnel.id,
            medication=funnel.medication,
            pills_dispensed=prescription.dosage
        )
        db.session.add(history)

    db.session.commit()

    # Send the dispense event to all connected clients
    send_dispense_event(dispense_data)

    return jsonify(dispense_data)


@app.route('/patient/<int:patient_id>/history')
def patient_history(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    history = DispenseHistory.query.filter_by(patient_id=patient_id).order_by(
        DispenseHistory.dispense_time.desc()).all()
    return render_template('patient_history.html', patient=patient, history=history)


@app.route('/events')
def events():
    def event_stream():
        # Add this connection to active_connections
        active_connections.add(request)
        try:
            while True:
                # Keep the connection alive
                yield "data: {\"type\": \"ping\"}\n\n"
                import time
                time.sleep(30)
        finally:
            # Remove connection when client disconnects
            active_connections.remove(request)

    return Response(event_stream(), mimetype='text/event-stream')


# Create the database and tables
with app.app_context():
    db.drop_all()  # Drop all tables to recreate with new schema
    db.create_all()
    create_default_funnels()

if __name__ == '__main__':
    # This makes Flask accessible from other devices on the network
    app.run(debug=True, host='0.0.0.0', port=10000)
