from datetime import date

from models import Assignment, Attendance, Document, Enrollment, Notice, StudentRequest, Submission


def _matches_class_target(item, user) -> bool:
    if getattr(item, "department", None) and item.department != user.department:
        return False
    if getattr(item, "academic_year", None) and item.academic_year != user.academic_year:
        return False
    if getattr(item, "section", None) and item.section != user.section:
        return False
    return True


def _to_iso(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def build_student_dashboard_context(db, user, ai_question=None, ai_response=None):
    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == user.id)
        .order_by(Enrollment.enrolled_at.desc())
        .all()
    )
    course_ids = [enrollment.course_id for enrollment in enrollments if enrollment.course_id]

    assignments = []
    all_assignments = db.query(Assignment).order_by(Assignment.due_date.asc()).all()
    for item in all_assignments:
        course_match = item.course_id in course_ids if course_ids else False
        class_match = _matches_class_target(item, user)
        if course_match or class_match:
            assignments.append(item)

    submissions = db.query(Submission).filter(Submission.student_id == user.id).all()
    submitted_assignment_ids = {submission.assignment_id for submission in submissions}
    request_rows = (
        db.query(StudentRequest)
        .filter(StudentRequest.student_id == user.id)
        .order_by(StudentRequest.created_at.desc(), StudentRequest.id.desc())
        .limit(20)
        .all()
    )

    attendance_rows = db.query(Attendance).filter(Attendance.student_id == user.id).all()
    attendance_total = len(attendance_rows)
    attendance_present = len([row for row in attendance_rows if row.status == "present"])
    attendance_percentage = round((attendance_present / attendance_total) * 100, 2) if attendance_total else 0

    request_counts = {"pending": 0, "approved": 0, "rejected": 0}
    for item in request_rows:
        if item.status in request_counts:
            request_counts[item.status] += 1

    request_advice = None
    if attendance_percentage < 75:
        request_advice = "Attendance is below 75%, so leave-related requests may receive closer review."

    notices_all = db.query(Notice).order_by(Notice.created_at.desc()).limit(30).all()
    docs_all = db.query(Document).order_by(Document.created_at.desc()).limit(30).all()
    notices = [item for item in notices_all if _matches_class_target(item, user)]
    documents = [item for item in docs_all if _matches_class_target(item, user)]

    return {
        "user": user,
        "enrollments": enrollments,
        "assignments": assignments,
        "submitted_assignment_ids": submitted_assignment_ids,
        "requests": request_rows,
        "request_counts": request_counts,
        "attendance_percentage": attendance_percentage,
        "request_advice": request_advice,
        "notices": notices,
        "documents": documents,
        "ai_question": ai_question,
        "ai_response": ai_response,
        "dashboard_ui_data": {
            "studentName": user.full_name,
            "department": user.department or "-",
            "academicYear": user.academic_year,
            "section": user.section or "-",
            "attendancePercentage": attendance_percentage,
            "requestCounts": request_counts,
            "stats": [
                {"label": "Enrolled courses", "value": len(enrollments)},
                {"label": "Visible assignments", "value": len(assignments)},
                {"label": "Pending requests", "value": request_counts["pending"]},
            ],
            "requests": [
                {
                    "id": item.id,
                    "category": item.category,
                    "title": item.title,
                    "status": item.status,
                    "createdAt": _to_iso(item.created_at),
                    "remark": item.admin_remark or "",
                }
                for item in request_rows[:6]
            ],
            "assignments": [
                {
                    "id": item.id,
                    "title": item.title,
                    "dueDate": _to_iso(item.due_date),
                    "submitted": item.id in submitted_assignment_ids,
                }
                for item in assignments[:6]
            ],
            "notices": [
                {
                    "id": item.id,
                    "title": item.title,
                    "category": item.category,
                    "createdAt": _to_iso(item.created_at),
                }
                for item in notices[:5]
            ],
        },
    }
