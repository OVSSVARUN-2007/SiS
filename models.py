from sqlalchemy import (
    TIMESTAMP,
    Column,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship

from database import Base


class StudentRegister(Base):
    __tablename__ = "student_register"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    phone = Column(String(15), unique=True, nullable=True)
    password = Column(String(255), nullable=False)
    gender = Column(Enum("male", "female", "other"), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    department = Column(String(100), nullable=True, index=True)
    academic_year = Column(Integer, nullable=True, index=True)
    section = Column(String(20), nullable=True, index=True)
    role = Column(Enum("student", "admin"), nullable=True, server_default="student")
    is_active = Column(Integer, nullable=True, server_default=text("1"))
    email_verified = Column(Integer, nullable=True, server_default=text("0"))
    email_otp_code = Column(String(10), nullable=True)
    email_otp_expires_at = Column(TIMESTAMP, nullable=True)
    email_otp_sent_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        TIMESTAMP,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    role = Column(Enum("student", "admin"), nullable=True, server_default="student")
    created_at = Column(TIMESTAMP, nullable=True, server_default=text("CURRENT_TIMESTAMP"))


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    instructor = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=text("CURRENT_TIMESTAMP"))


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("student_register.id"), nullable=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    enrolled_at = Column(TIMESTAMP, nullable=True, server_default=text("CURRENT_TIMESTAMP"))

    student = relationship("StudentRegister")
    course = relationship("Course")


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(Date, nullable=True)
    department = Column(String(100), nullable=True, index=True)
    academic_year = Column(Integer, nullable=True, index=True)
    section = Column(String(20), nullable=True, index=True)

    course = relationship("Course")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True, index=True)
    student_id = Column(Integer, ForeignKey("student_register.id"), nullable=True, index=True)
    content = Column(Text, nullable=True)
    marks = Column(Integer, nullable=True)
    submitted_at = Column(TIMESTAMP, nullable=True, server_default=text("CURRENT_TIMESTAMP"))

    assignment = relationship("Assignment")
    student = relationship("StudentRegister")


class StudentRequest(Base):
    __tablename__ = "student_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("student_register.id"), nullable=False, index=True)
    category = Column(
        Enum("bonafide", "leave", "certificate"),
        nullable=False,
        server_default="bonafide",
    )
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    proof_url = Column(String(500), nullable=True)
    status = Column(
        Enum("pending", "approved", "rejected"),
        nullable=False,
        server_default="pending",
    )
    admin_remark = Column(Text, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("student_register.id"), nullable=True, index=True)
    reviewed_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        TIMESTAMP,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    student = relationship("StudentRegister", foreign_keys=[student_id])
    reviewer = relationship("StudentRegister", foreign_keys=[reviewed_by])


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("student_register.id"), nullable=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    date = Column(Date, nullable=True)
    status = Column(Enum("present", "absent"), nullable=True)
    department = Column(String(100), nullable=True, index=True)
    academic_year = Column(Integer, nullable=True, index=True)
    section = Column(String(20), nullable=True, index=True)
    marked_by = Column(Integer, ForeignKey("student_register.id"), nullable=True, index=True)

    student = relationship("StudentRegister", foreign_keys=[student_id])
    marker = relationship("StudentRegister", foreign_keys=[marked_by])
    course = relationship("Course")


class AIQuery(Base):
    __tablename__ = "ai_queries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("student_register.id"), nullable=True, index=True)
    question = Column(Text, nullable=True)
    response = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=text("CURRENT_TIMESTAMP"))

    student = relationship("StudentRegister")


class Notice(Base):
    __tablename__ = "notices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    category = Column(Enum("notice", "internship", "job"), nullable=False, server_default="notice")
    department = Column(String(100), nullable=True, index=True)
    academic_year = Column(Integer, nullable=True, index=True)
    section = Column(String(20), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("student_register.id"), nullable=True, index=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=text("CURRENT_TIMESTAMP"))

    admin = relationship("StudentRegister")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    file_url = Column(String(500), nullable=False)
    category = Column(Enum("document", "internship", "job"), nullable=False, server_default="document")
    department = Column(String(100), nullable=True, index=True)
    academic_year = Column(Integer, nullable=True, index=True)
    section = Column(String(20), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("student_register.id"), nullable=True, index=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=text("CURRENT_TIMESTAMP"))

    admin = relationship("StudentRegister")
