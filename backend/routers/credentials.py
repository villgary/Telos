from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models, schemas, auth, encryption

router = APIRouter(prefix="/api/v1/credentials", tags=["凭据管理"])


@router.get("", response_model=list[schemas.CredentialResponse])
async def list_credentials(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """
    List all credentials (admin only).
    NEVER returns plaintext password or private key.
    """
    creds = db.query(models.Credential).all()
    return [schemas.CredentialResponse.from_orm_full(c) for c in creds]


@router.post("", response_model=schemas.CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    cred_in: schemas.CredentialCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Create a new credential (admin only)."""
    existing = db.query(models.Credential).filter(models.Credential.name == cred_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="凭据名称已存在")

    if cred_in.auth_type == models.AuthType.password:
        if not cred_in.password:
            raise HTTPException(status_code=400, detail="密码不能为空")
        password_enc = encryption.encrypt(cred_in.password)
        private_key_enc = None
        passphrase_enc = None
    else:
        if not cred_in.private_key:
            raise HTTPException(status_code=400, detail="SSH 私钥不能为空")
        password_enc = None
        private_key_enc = encryption.encrypt(cred_in.private_key)
        passphrase_enc = encryption.encrypt(cred_in.passphrase) if cred_in.passphrase else None

    cred = models.Credential(
        name=cred_in.name,
        auth_type=cred_in.auth_type,
        username=cred_in.username,
        password_enc=password_enc,
        private_key_enc=private_key_enc,
        passphrase_enc=passphrase_enc,
        created_by=user.id,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return schemas.CredentialResponse.from_orm_full(cred)


@router.get("/{cred_id}", response_model=schemas.CredentialResponse)
async def get_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    cred = db.query(models.Credential).filter(models.Credential.id == cred_id).first()
    if not cred:
        raise HTTPException(status_code=404, detail="凭据不存在")
    return schemas.CredentialResponse.from_orm_full(cred)


@router.put("/{cred_id}", response_model=schemas.CredentialResponse)
async def update_credential(
    cred_id: int,
    update_in: schemas.CredentialUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Update credential name, username, or password."""
    cred = db.query(models.Credential).filter(models.Credential.id == cred_id).first()
    if not cred:
        raise HTTPException(status_code=404, detail="凭据不存在")

    if update_in.name is not None:
        existing = db.query(models.Credential).filter(
            models.Credential.name == update_in.name,
            models.Credential.id != cred_id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="凭据名称已被占用")
        cred.name = update_in.name
    if update_in.username is not None:
        cred.username = update_in.username
    if update_in.password is not None:
        cred.password_enc = encryption.encrypt(update_in.password)
    if update_in.private_key is not None:
        cred.private_key_enc = encryption.encrypt(update_in.private_key)
    if update_in.passphrase is not None:
        cred.passphrase_enc = encryption.encrypt(update_in.passphrase)

    db.commit()
    db.refresh(cred)
    return schemas.CredentialResponse.from_orm_full(cred)


@router.delete("/{cred_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.require_role(models.UserRole.admin)),
):
    """Delete a credential. Fails if any asset references it."""
    cred = db.query(models.Credential).filter(models.Credential.id == cred_id).first()
    if not cred:
        raise HTTPException(status_code=404, detail="凭据不存在")
    if cred.assets:
        raise HTTPException(status_code=400, detail="此凭据仍被资产引用，无法删除")
    db.delete(cred)
    db.commit()
