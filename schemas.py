from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    first_name: str
    profile_pic: Optional[str] = None

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PostBase(BaseModel):
    content: str
    image_url: Optional[str] = None

class PostCreate(BaseModel):
    content: str
    user_id: str

class Post(PostBase):
    id: str
    user_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DeletePostResponse(BaseModel):
    message: str
    post_id: str

    model_config = ConfigDict(from_attributes=True)

class CommentBase(BaseModel):
    content: str

class CommentCreate(CommentBase):
    post_id: str
    user_id: str

class Comment(CommentBase):
    id: str
    post_id: str
    user_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ReactionBase(BaseModel):
    type: str

class ReactionCreate(ReactionBase):
    post_id: str
    user_id: str

class Reaction(ReactionBase):
    id: str
    post_id: str
    user_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)