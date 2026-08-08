from src.schemas.common import BoolField
from src.schemas.subject import (
    SubjectReadSchema,
    SubjectStudentReadSchema,
    TopicReadSchema,
    TopicStudentReadSchema,
)
from src.schemas.task import (
    AttachmentReadSchema,
    StudentAttemptReadSchema,
    TaskChoiceReadSchema,
    TaskFileReadSchema,
    TaskReadBaseSchema,
    TaskReadSchema,
    TaskSubmissionReadSchema,
    TaskTextReadSchema,
)
from src.schemas.user import (
    UserAuthorizationSchema,
    UserBriefSchema,
    UserNameSchema,
    UserReadSchema,
    UserRegistrationSchema,
)

__all__ = [
    "BoolField",
    "UserAuthorizationSchema",
    "UserNameSchema",
    "UserRegistrationSchema",
    "UserBriefSchema",
    "UserReadSchema",
    "SubjectReadSchema",
    "SubjectStudentReadSchema",
    "TopicReadSchema",
    "TopicStudentReadSchema",
    "AttachmentReadSchema",
    "TaskReadBaseSchema",
    "TaskChoiceReadSchema",
    "TaskTextReadSchema",
    "TaskFileReadSchema",
    "TaskReadSchema",
    "StudentAttemptReadSchema",
    "TaskSubmissionReadSchema",
]
