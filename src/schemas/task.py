from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.common import BoolField


class AttachmentReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    file_path: str
    file_name: str


class TaskReadBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    topic_id: int
    created_by: int | None = None
    is_public: BoolField
    question_type: Literal['choice', 'text', 'file', 'material']
    can_retry: BoolField = False

    attachments: list[AttachmentReadSchema] = Field(default_factory=list)


class TaskChoiceReadSchema(TaskReadBaseSchema):
    question_type: Literal['choice']

    options: list[str] = Field(default_factory=list)
    correct_options: list[str] = Field(default_factory=list)
    multiple_correct: BoolField = False
    shuffle_options: BoolField = False


class TaskTextReadSchema(TaskReadBaseSchema):
    question_type: Literal['text']

    correct_answer: str = ''
    is_case_sensitive: BoolField = False
    max_length: Optional[int] = None


class TaskFileReadSchema(TaskReadBaseSchema):
    question_type: Literal['file', 'material']

    max_file_size: Optional[int] = None
    allowed_types: list[str] | None = None
    is_material: BoolField = False


TaskReadSchema = Annotated[
    Union[TaskChoiceReadSchema, TaskTextReadSchema, TaskFileReadSchema],
    Field(discriminator='question_type'),
]


class StudentAttemptReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    task_id: int
    is_correct: Optional[BoolField] = None
    answer_text: Optional[str] = None
    file_path: Optional[str] = None


class TaskSubmissionReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    surname: str
    first_name: str
    patronymic: str
    file_path: Optional[str] = None
    answer_text: Optional[str] = None
    is_correct: Optional[BoolField] = None
