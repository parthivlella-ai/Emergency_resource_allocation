import os
import copy
import logging
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify

from config import Config
from database import init_db, get_db, get_db_info
from models import (
    Incident, Zone, ZoneFeature, ResourceInventory, ResourceAllocation,
    ResponsePlan, CommunicationLog, AuditLog, DataSnapshot, RescueTeam, MonitoringEvent
)

# Import AI Agents, Orchestrator, and MCP
from agents.orchestrator import IncidentOrchestrator
from agents.communication_agent import CommunicationAgent
from agents.monitoring_agent import MonitoringAgent
from services.mcp_service import MCPService

from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# Enable CORS for Vercel <-> Render cross-origin deployment
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize database schema safely
init_db()

# Orchestrator and agent singletons
orchestrator = IncidentOrchestrator()
communication_agent = CommunicationAgent()
monitoring_agent = MonitoringAgent()
mcp_service = MCPService()

@app.route('/health', methods=['GET'])
def health_check():
    """Render and Vercel Health Check Endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'Emergency Resource Allocation Command Center',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200

@app.route('/api/incident/baseline', methods=['GET'])
def api_baseline_incident():
    """
    Returns baseline disaster analysis data as JSON.
    Allows static frontends (e.g. deployed on Vercel) to initialize cleanly.
    """
    location_str = request.args.get('location', 'Vijayawada, Andhra Pradesh')
    disaster_type = request.args.get('disaster_type', 'Flood')
    res = orchestrator.process_incident(
        disaster_type=disaster_type,
        location_str=location_str,
        severity_notes="Initial baseline operational telemetry active."
    )
    return jsonify(res)

@app.route('/', methods=['GET'])
def index():
    """
    Command Center Landing Dashboard:
    Simple automated disaster intake requiring only:
      1. Disaster Type
      2. Affected City / Area
      3. Incident Severity Notes (Optional)
    """
    db_info = get_db_info()

    # Preload baseline analysis for Vijayawada
    baseline_res = orchestrator.process_incident(
        disaster_type="Flood",
        location_str="Vijayawada, Andhra Pradesh",
        severity_notes="Regional flood monitoring active. Real-world telemetry initialized."
    )

    return render_template(
        'index.html',
        db_info=db_info,
        initial_incident=baseline_res['incident'],
        normalized_location=baseline_res['normalized_location'],
        weather=baseline_res['weather'],
        results=baseline_res,
        decision_card=baseline_res['decision_card'],
        response_plan=baseline_res['response_plan'],
        zones=baseline_res['zones'],
        totals=baseline_res['totals'],
        telemetry_sources=baseline_res.get('telemetry_sources', []),
        shortage_audit=baseline_res.get('shortage_audit', {}),
        rescue_teams=baseline_res.get('rescue_teams', [])
    )

@app.route('/api/incident/analyze', methods=['POST'])
def api_analyze_incident():
    """
    Main Automated AI Incident Intake Endpoint:
    Officer inputs only: Disaster Type, Affected City/Area, and optional notes.
    The system automatically executes the multi-agent pipeline:
      Location -> Data Collection -> ML Risk -> Priority -> Shortage Audit ->
      Resource Allocation -> Response Plan -> Team Assignment.
    """
    try:
        data = request.get_json(force=True) or {}
        disaster_type = data.get('disaster_type', 'Flood')
        location_str = data.get('location', '').strip()
        severity_notes = data.get('severity_notes', '')

        if not location_str:
            return jsonify({'success': False, 'error': 'Please enter an affected city or regional operations area.'}), 400

        custom_resources = data.get('resources')

        # Execute full multi-agent orchestration
        result = orchestrator.process_incident(
            disaster_type=disaster_type,
            location_str=location_str,
            severity_notes=severity_notes,
            custom_resources=custom_resources
        )

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error analyzing incident: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/incident/<int:incident_id>/approve', methods=['POST'])
def api_approve_dispatch(incident_id):
    """
    Authorized Human Approval & Emergency Dispatch Endpoint:
    Ensures an AI agent never dispatches emergency units independently.
    Requires authorized officer confirmation, executes targeted transmissions,
    and updates immutable audit trail.
    """
    try:
        data = request.get_json(force=True) or {}
        officer_name = data.get('officer_name', 'Command Duty Officer').strip()
        badge_number = data.get('badge_number', 'NDMA-7741').strip()

        dispatch_result = communication_agent.execute_authorized_dispatch(
            incident_db_id=incident_id,
            officer_name=officer_name,
            badge_number=badge_number
        )

        return jsonify(dispatch_result)
    except Exception as e:
        logger.error(f"Error authorizing dispatch for incident #{incident_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/incident/<int:incident_id>/team/<team_id>/respond', methods=['POST'])
def api_team_respond(incident_id, team_id):
    """
    Emergency Responder Acknowledgement Endpoint:
    Records real-time team response: ACCEPTED, DECLINED, or UNAVAILABLE.
    If a squad declines, the system records a shortage and flags reserve units.
    """
    try:
        data = request.get_json(force=True) or {}
        action = data.get('action', 'ACCEPTED')

        ack_result = communication_agent.record_team_response(
            incident_db_id=incident_id,
            team_id=team_id,
            response_action=action
        )
        return jsonify(ack_result)
    except Exception as e:
        logger.error(f"Error recording team response: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/incident/<int:incident_id>/escalate', methods=['POST'])
def api_simulate_escalation(incident_id):
    """
    Continuous Monitoring & Hydrologic Escalation Simulation:
    Re-evaluates zones under sudden cloudburst or dam discharge.
    Detects risk shifts (HIGH -> CRITICAL) and recommends delta asset reallocation.
    Enforces that new resources require human officer re-approval before dispatch.
    """
    try:
        data = request.get_json(force=True) or {}
        rainfall_surge_mm = float(data.get('rainfall_surge_mm', 45.0))
        dam_release = bool(data.get('dam_release', True))

        escalation_result = monitoring_agent.simulate_weather_escalation(
            incident_db_id=incident_id,
            rainfall_surge_mm=rainfall_surge_mm,
            dam_discharge_active=dam_release
        )

        return jsonify({'success': True, 'escalation': escalation_result})
    except Exception as e:
        logger.error(f"Error simulating escalation for incident #{incident_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/incident/<int:incident_id>/audit', methods=['GET'])
def api_get_audit_logs(incident_id):
    """Retrieves chronological audit trail for incident accountability."""
    try:
        with get_db() as session:
            logs = session.query(AuditLog).filter_by(incident_id=incident_id).order_by(AuditLog.timestamp.asc()).all()
            return jsonify({'success': True, 'audit_trail': [l.to_dict() for l in logs]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/incident/<int:incident_id>/snapshots', methods=['GET'])
def api_get_snapshots(incident_id):
    """Retrieves raw data snapshots for full data provenance transparency."""
    try:
        with get_db() as session:
            snaps = session.query(DataSnapshot).filter_by(incident_id=incident_id).all()
            return jsonify({'success': True, 'snapshots': [s.to_dict() for s in snaps]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/incident/<int:incident_id>/communications', methods=['GET'])
def api_get_communications(incident_id):
    """Retrieves transmission logs for responder notifications."""
    try:
        with get_db() as session:
            comms = session.query(CommunicationLog).filter_by(incident_id=incident_id).order_by(CommunicationLog.sent_at.desc()).all()
            return jsonify({'success': True, 'communications': [c.to_dict() for c in comms]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/teams', methods=['GET'])
def api_get_teams():
    """Returns registered emergency response squads from PostgreSQL."""
    try:
        with get_db() as session:
            teams = session.query(RescueTeam).all()
            return jsonify({'success': True, 'teams': [t.to_dict() for t in teams]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/incidents', methods=['GET'])
def api_get_recent_incidents():
    """Lists recent operational incidents from PostgreSQL."""
    try:
        with get_db() as session:
            incidents = session.query(Incident).order_by(Incident.created_at.desc()).limit(15).all()
            return jsonify({'success': True, 'incidents': [i.to_dict() for i in incidents]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/mcp/manifest', methods=['GET'])
def api_mcp_manifest():
    """Returns Model Context Protocol (MCP) tool manifest."""
    return jsonify(mcp_service.get_manifest())

@app.route('/api/mcp/call', methods=['POST'])
def api_mcp_call():
    """Executes an MCP tool call."""
    try:
        data = request.get_json(force=True) or {}
        tool_name = data.get("name")
        arguments = data.get("arguments", {})
        result = mcp_service.execute_tool(tool_name, arguments)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/db_status', methods=['GET'])
def api_db_status():
    """Returns database connection status."""
    return jsonify(get_db_info())

# Backwards compatibility routes
@app.route('/predict_and_allocate', methods=['POST'])
def legacy_predict_and_allocate():
    try:
        req_json = request.get_json(force=True) or {}
        location = req_json.get('assessment_name', 'Vijayawada Regional Sector')
        resources = req_json.get('resources')
        result = orchestrator.process_incident("Flood", location, custom_resources=resources)
        return jsonify({
            'success': True,
            'assessment_id': result['incident']['id'],
            'results': {
                'zones': result['zones'],
                'totals': result['totals'],
                'decision_card': result['decision_card']
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/assessments', methods=['GET'])
def legacy_assessments():
    return api_get_recent_incidents()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
