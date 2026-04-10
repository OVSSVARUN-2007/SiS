from models import Assignment, Document, Enrollment, Notice, Submission


def _matches_class_target(item, user) -> bool:
    if getattr(item, "department", None) and item.department != user.department:
        return False
    if getattr(item, "academic_year", None) and item.academic_year != user.academic_year:
        return False
    if getattr(item, "section", None) and item.section != user.section:
        return False
    return True


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

    notices_all = db.query(Notice).order_by(Notice.created_at.desc()).limit(30).all()
    docs_all = db.query(Document).order_by(Document.created_at.desc()).limit(30).all()
    notices = [item for item in notices_all if _matches_class_target(item, user)]
    documents = [item for item in docs_all if _matches_class_target(item, user)]

    return {
        "user": user,
        "enrollments": enrollments,
        "assignments": assignments,
        "submitted_assignment_ids": submitted_assignment_ids,
        "notices": notices,
        "documents": documents,
        "ai_question": ai_question,
        "ai_response": ai_response,
    }
