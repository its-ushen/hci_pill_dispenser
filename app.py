from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import json
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

# Change this to a secure secret key
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pill_dispenser.db'
db = SQLAlchemy(app)

# Store WebSocket connections
websocket_clients = set()

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


@sock.route('/ws')
def websocket_endpoint(ws):
    """WebSocket endpoint for real-time communication"""
    print("New WebSocket client connected")
    websocket_clients.add(ws)

    try:
        while True:
            try:
                # Send periodic ping to keep connection alive
                ws.send(json.dumps({"type": "ping"}))
                # Wait for pong or any message
                message = ws.receive(timeout=10)  # Add timeout
                if message:
                    print(f"Received from client: {message}")
                    try:
                        data = json.loads(message)
                        if data.get("type") == "pong":
                            print("Received pong from client")
                    except json.JSONDecodeError:
                        print("Received non-JSON message")
            except Exception as e:
                print(f"Error in WebSocket communication: {e}")
                break
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print("WebSocket client disconnected")
        if ws in websocket_clients:
            websocket_clients.remove(ws)


def send_dispense_event(data):
    """Send dispense event to all connected WebSocket clients"""
    message = json.dumps(data)
    print(f"Sending dispense event to {len(websocket_clients)} clients")
    disconnected_clients = set()

    for client in websocket_clients:
        try:
            client.send(message)
            print(f"Successfully sent dispense event to client")
        except Exception as e:
            print(f"Error sending to client: {e}")
            disconnected_clients.add(client)

    # Remove disconnected clients
    for client in disconnected_clients:
        websocket_clients.remove(client)
        print("Removed disconnected client")


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

    # Add debug logging
    print("Sending dispense event:", dispense_data)

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
    print("Event sent to queue")

    return jsonify(dispense_data)


@app.route('/patient/<int:patient_id>/history')
def patient_history(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    history = DispenseHistory.query.filter_by(patient_id=patient_id).order_by(
        DispenseHistory.dispense_time.desc()).all()
    return render_template('patient_history.html', patient=patient, history=history)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_default_funnels()

    # Use Flask's development server when running locally
    if os.environ.get('RENDER') != 'true':
        app.run(debug=True, host='0.0.0.0', port=10000)
    else:
        # On Render, let their system handle the server
        print("Running on Render - using production server")
