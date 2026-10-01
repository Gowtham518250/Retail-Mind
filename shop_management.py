    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/online-settings")
def get_online_settings(user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Owner-only settings used exclusively by online marketplace orders."""
    try:
        profile = ShopService.get_shop_profile(db, user_id)
        return {
            "is_online_store_enabled": bool(profile.is_online_store_enabled),
            "online_setup_fee": float(getattr(profile, "online_setup_fee", 0) or 0),
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/online-settings")
def set_online_settings(
    data: dict,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    """Update online-only setup/service fee. This never changes POS prices."""
    try:
        profile = ShopService.get_shop_profile(db, user_id)
        raw_fee = data.get("online_setup_fee", 0)
        try:
            fee = round(float(raw_fee), 2)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Online setup fee must be a valid number.")

        if fee < 0 or fee > 100000:
            raise HTTPException(
                status_code=422,
                detail="Online setup fee must be between ₹0 and ₹100000.",
            )

        profile.online_setup_fee = fee
        db.commit()
        return {
            "success": True,
            "online_setup_fee": fee,
            "message": "Online-only setup fee updated.",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update online settings: {str(e)}")


@router.get("/publish-status")
def get_publish_status(user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Get the shop's online store publishing status"""
    try:
        profile = ShopService.get_shop_profile(db, user_id)
        return {"is_published": profile.is_online_store_enabled or False}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/publish-status")
def set_publish_status(data: dict, user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Set the shop's online store publishing status"""
    try:
        is_published = data.get("is_published", False)
        profile = ShopService.get_shop_profile(db, user_id)
        profile.is_online_store_enabled = is_published
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update publish status: {str(e)}")
        return {
            "success": True, 
            "is_published": is_published, 
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/publish-marketplace")
def publish_marketplace(data: dict, user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Publish the shop to marketplace with coordinates"""
    try:
        profile = ShopService.get_shop_profile(db, user_id)
        profile.latitude = data.get("latitude")
        profile.longitude = data.get("longitude")
        profile.is_online_store_enabled = True
        
        if data.get("address_nickname"):
            profile.location = data.get("address_nickname")
            
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to publish marketplace: {str(e)}")
        slug = profile.shop_name.lower().replace(" ", "-") if profile.shop_name else str(profile.id)
        return {
            "success": True,
            "shop_id": profile.id,
            "marketplace_url": f"https://shop.retailmind.com/{slug}",
            "published_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/publish-marketplace")
def unpublish_marketplace(user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    """Unpublish the shop from marketplace"""