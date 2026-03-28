from flask import Blueprint, jsonify, request
from ppm_model import WorkOrderModel
from ppm_mailer import send_maintenance_email # Import the general mailer for notifications
from datetime import datetime

workflow_api = Blueprint('workflow_api', __name__)

@workflow_api.route('/api/workflow/assign', methods=['POST'])
def assign_work_order():
    """
    Action: Supervisor assigns a WO to a specific technician.
    Triggered when Supervisor clicks 'Assign' on the Dashboard.
    """
    data = request.json
    wo_id = data.get('work_order_id')
    technician_name = data.get('technician_name')

    if not wo_id or not technician_name:
        return jsonify({"error": "Missing WO ID or Technician Name"}), 400

    all_data = WorkOrderModel.load_orders()
    found = False

    for wo in all_data['work_orders']:
        if wo['work_order_id'] == wo_id:
            wo['status'] = 'in-progress'
            wo['assigned_to'] = technician_name
            wo['assigned_at'] = datetime.now().isoformat()
            found = True
            break

    if found:
        WorkOrderModel.save_orders(all_data)
        # Optional: Notify technician via email
        # send_maintenance_email(f"New Task: {wo_id}", f"You have been assigned to: {wo_id}")
        return jsonify({"status": "success", "message": f"Assigned to {technician_name}"})
    
    return jsonify({"error": "Work Order not found"}), 404

@workflow_api.route('/api/workflow/close', methods=['POST'])
def close_work_order():
    """
    Action: Technician/Supervisor marks work as complete.
    Enforces the rule: Cost and Remarks must be captured.
    """
    data = request.json
    wo_id = data.get('work_order_id')
    remarks = data.get('remarks', 'No remarks provided')
    cost = data.get('cost', 0)

    all_data = WorkOrderModel.load_orders()
    found = False

    for wo in all_data['work_orders']:
        if wo['work_order_id'] == wo_id:
            wo['status'] = 'closed'
            wo['closed_at'] = datetime.now().isoformat()
            wo['execution_details']['remarks'] = remarks
            wo['execution_details']['cost'] = cost
            found = True
            break

    if found:
        WorkOrderModel.save_orders(all_data)
        return jsonify({"status": "success", "message": "Work Order Closed and Logged to History"})
    
    return jsonify({"error": "Work Order not found"}), 404

@workflow_api.route('/api/workflow/pending_assignment', methods=['GET'])
def get_pending_mail_check():
    """
    Action: Simulates the 'Supervisor checked mail' view.
    Returns only work orders that are 'open' and 'unassigned'.
    """
    all_data = WorkOrderModel.load_orders()
    pending = [wo for wo in all_data['work_orders'] if wo['status'] == 'open' and wo['assigned_to'] == "Supervisor Check Pending"]
    return jsonify(pending)