import os
import shutil
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import List, Optional
import models
import schemas
from database import get_db, engine
from datetime import datetime
import uuid

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Social Media API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.post("/users/", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def create_user(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    try:
        db_user = models.User(
            first_name=user_data.first_name, profile_pic=user_data.profile_pic
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="User creation failed")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")


@app.put("/users/{user_id}/profile-picture", response_model=schemas.User)
def update_profile_picture(
    user_id: str, profile_pic: UploadFile = File(...), db: Session = Depends(get_db)
):
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not profile_pic.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        file_extension = os.path.splitext(profile_pic.filename)[1]
        filename = f"profile_{user_id}_{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(profile_pic.file, buffer)

        if user.profile_pic:
            try:
                old_filename = user.profile_pic.split("/")[-1]
                old_file_path = os.path.join(UPLOAD_DIR, old_filename)

                print(f"Attempting to delete old profile picture: {old_file_path}")

                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
                    print(f"Successfully deleted old profile picture: {old_file_path}")
                else:
                    print(f"Old profile picture not found: {old_file_path}")
            except Exception as e:
                print(f"Error deleting old profile picture: {e}")

        user.profile_pic = f"/uploads/{filename}"
        db.commit()
        db.refresh(user)

        print(f"Updated user {user.id} with new profile picture: {user.profile_pic}")

        return user
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Profile picture update failed")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")


@app.get("/users/{user_id}", response_model=schemas.User)
def get_user(user_id: str, db: Session = Depends(get_db)):
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error")


@app.post("/posts/", response_model=schemas.Post, status_code=status.HTTP_201_CREATED)
def create_post(
    content: str = Form(...),
    image: Optional[UploadFile] = None,
    user_id: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        image_url = None

        if image:
            if not image.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="File must be an image")

            file_extension = os.path.splitext(image.filename)[1]
            filename = f"{uuid.uuid4()}{file_extension}"
            file_path = os.path.join(UPLOAD_DIR, filename)

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)

            image_url = f"/uploads/{filename}"

        db_post = models.Post(content=content, image_url=image_url, user_id=user_id)
        db.add(db_post)
        db.commit()
        db.refresh(db_post)
        return db_post
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Post creation failed")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")


@app.get("/posts/", response_model=List[schemas.Post])
def get_posts(db: Session = Depends(get_db)):
    try:
        posts = db.query(models.Post).order_by(models.Post.created_at.desc()).all()
        return posts
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error")


@app.get("/posts/{post_id}", response_model=schemas.Post)
def get_post(post_id: str, db: Session = Depends(get_db)):
    try:
        post = db.query(models.Post).filter(models.Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        return post
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error")


@app.delete("/posts/{post_id}", status_code=status.HTTP_200_OK)
def delete_post(post_id: str, user_id: str, db: Session = Depends(get_db)):
    try:
        post = db.query(models.Post).filter(models.Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        if post.user_id != user_id:
            raise HTTPException(
                status_code=403, detail="You can only delete your own posts"
            )

        if post.image_url:
            image_path = post.image_url.replace("/uploads/", "")
            full_image_path = os.path.join(UPLOAD_DIR, image_path)
            if os.path.exists(full_image_path):
                os.remove(full_image_path)

        db.delete(post)
        db.commit()

        return {"message": "Post deleted successfully", "post_id": post_id}
    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")


@app.post(
    "/comments/", response_model=schemas.Comment, status_code=status.HTTP_201_CREATED
)
def create_comment(comment_data: schemas.CommentCreate, db: Session = Depends(get_db)):
    try:
        post = (
            db.query(models.Post).filter(models.Post.id == comment_data.post_id).first()
        )
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        user = (
            db.query(models.User).filter(models.User.id == comment_data.user_id).first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        db_comment = models.Comment(**comment_data.dict())
        db.add(db_comment)
        db.commit()
        db.refresh(db_comment)
        return db_comment
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Comment creation failed")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")


@app.get("/comments/{post_id}", response_model=List[schemas.Comment])
def get_comments(post_id: str, db: Session = Depends(get_db)):
    try:
        comments = (
            db.query(models.Comment)
            .filter(models.Comment.post_id == post_id)
            .order_by(models.Comment.created_at.asc())
            .all()
        )
        return comments
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error")
    
@app.delete("/comments/{comment_id}")
def delete_comment(comment_id: str, user_id: str, db: Session = Depends(get_db)):
    try:
        comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")
        
        if comment.user_id != user_id:
            raise HTTPException(
                status_code=403, 
                detail="You can only delete your own comments"
            )
        
        db.delete(comment)
        db.commit()
        
        return {
            "message": "Comment deleted successfully",
            "comment_id": comment_id
        }
    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")


@app.post("/reactions/", response_model=schemas.Reaction)
def create_reaction(reaction_data: schemas.ReactionCreate, db: Session = Depends(get_db)):
    try:
        post = db.query(models.Post).filter(models.Post.id == reaction_data.post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        user = db.query(models.User).filter(models.User.id == reaction_data.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        existing_reaction = db.query(models.Reaction).filter(
            models.Reaction.post_id == reaction_data.post_id,
            models.Reaction.user_id == reaction_data.user_id
        ).first()
        
        if reaction_data.type == 'unlike':
            if existing_reaction:
                db.delete(existing_reaction)
                db.commit()
                return {
                    "id": "removed",
                    "type": "unlike",
                    "post_id": reaction_data.post_id,
                    "user_id": reaction_data.user_id,
                    "created_at": datetime.now().isoformat()
                }
            else:
                raise HTTPException(status_code=404, detail="No reaction to remove")
        
        if existing_reaction:
            existing_reaction.type = reaction_data.type
            db.commit()
            db.refresh(existing_reaction)
            return existing_reaction
        else:
            db_reaction = models.Reaction(**reaction_data.dict())
            db.add(db_reaction)
            db.commit()
            db.refresh(db_reaction)
            return db_reaction
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Reaction creation failed")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")

@app.delete("/reactions/{post_id}/{user_id}")
def remove_reaction(post_id: str, user_id: str, db: Session = Depends(get_db)):
    try:
        reaction = db.query(models.Reaction).filter(
            models.Reaction.post_id == post_id,
            models.Reaction.user_id == user_id
        ).first()
        
        if not reaction:
            raise HTTPException(status_code=404, detail="Reaction not found")
        
        db.delete(reaction)
        db.commit()
        
        return {"message": "Reaction removed successfully"}
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")


@app.get("/reactions/{post_id}", response_model=List[schemas.Reaction])
def get_reactions(post_id: str, db: Session = Depends(get_db)):
    try:
        reactions = (
            db.query(models.Reaction).filter(models.Reaction.post_id == post_id).all()
        )
        return reactions
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error")


@app.get("/reactions/{post_id}/count")
def get_reaction_count(post_id: str, db: Session = Depends(get_db)):
    try:
        count = (
            db.query(models.Reaction).filter(models.Reaction.post_id == post_id).count()
        )
        return {"count": count}
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error")


@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "PostgreSQL"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
