-- Add group_id column to exams table
ALTER TABLE exams ADD COLUMN group_id INT;
ALTER TABLE exams ADD CONSTRAINT fk_exam_group FOREIGN KEY (group_id) REFERENCES groups(id);
