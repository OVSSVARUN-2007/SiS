USE sis;

ALTER TABLE student_register
  ADD COLUMN department VARCHAR(100) NULL AFTER date_of_birth,
  ADD COLUMN academic_year INT NULL AFTER department,
  ADD COLUMN section VARCHAR(20) NULL AFTER academic_year;

ALTER TABLE assignments
  ADD COLUMN department VARCHAR(100) NULL AFTER due_date,
  ADD COLUMN academic_year INT NULL AFTER department,
  ADD COLUMN section VARCHAR(20) NULL AFTER academic_year;

ALTER TABLE attendance
  ADD COLUMN department VARCHAR(100) NULL AFTER status,
  ADD COLUMN academic_year INT NULL AFTER department,
  ADD COLUMN section VARCHAR(20) NULL AFTER academic_year,
  ADD COLUMN marked_by INT NULL AFTER section;

CREATE TABLE IF NOT EXISTS notices (
  id INT NOT NULL AUTO_INCREMENT,
  title VARCHAR(200) NOT NULL,
  message TEXT NOT NULL,
  category ENUM('notice','internship','job') NOT NULL DEFAULT 'notice',
  department VARCHAR(100) NULL,
  academic_year INT NULL,
  section VARCHAR(20) NULL,
  created_by INT NULL,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_notices_created_by (created_by),
  CONSTRAINT fk_notices_created_by FOREIGN KEY (created_by) REFERENCES student_register(id)
);

CREATE TABLE IF NOT EXISTS documents (
  id INT NOT NULL AUTO_INCREMENT,
  title VARCHAR(200) NOT NULL,
  description TEXT NULL,
  file_url VARCHAR(500) NOT NULL,
  category ENUM('document','internship','job') NOT NULL DEFAULT 'document',
  department VARCHAR(100) NULL,
  academic_year INT NULL,
  section VARCHAR(20) NULL,
  created_by INT NULL,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_documents_created_by (created_by),
  CONSTRAINT fk_documents_created_by FOREIGN KEY (created_by) REFERENCES student_register(id)
);
