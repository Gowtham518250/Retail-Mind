# ✅ AI SHOP PRO - PRODUCTION DEPLOYMENT CHECKLIST
## Enterprise Retail Management System v3.0.0

**Deploy Date:** ___________  
**Deployed By:** ___________  
**Environment:** Production / Staging  
**Database URL:** ___________  

---

## 📋 PRE-DEPLOYMENT PHASE (Do This First)

### Code & Files
- [ ] All changes committed to Git
- [ ] Code reviewed and approved
- [ ] No hardcoded credentials in code
- [ ] `.env` variables documented in `.env.example`
- [ ] `.env` file NOT committed to Git
- [ ] All required files present:
  - [ ] `app.py`
  - [ ] `models.py`
  - [ ] `requirements.txt`
  - [ ] `migration_production_v1.sql`
  - [ ] `.env` (configured)

### Dependencies
- [ ] Run `pip install -r requirements.txt`
- [ ] Check Python version: `python --version` (should be 3.9+)
- [ ] Verify all packages installed: `pip list`
- [ ] No import errors: `python -c "from app import api"`

### Environment Setup
- [ ] `.env` file created with all required variables
- [ ] `DATABASE_URL` pointing to production database
- [ ] `REDIS_URL` pointing to Redis instance
- [ ] `SECRET_KEY` generated (min 32 chars)
- [ ] `SMTP_SERVER` & credentials configured
- [ ] `FRONTEND_URL` set correctly
- [ ] All sensitive data stored in `.env`, not in code

### Database Preparation
- [ ] Database exists and is accessible
- [ ] Test connection: `psql $DATABASE_URL -c "SELECT 1;"`
- [ ] Backup created: `pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql`
- [ ] Migration script reviewed: `migration_production_v1.sql`
- [ ] No uncommitted schema changes

### Validation
- [ ] Run pre-deployment validation: `python validate_production.py`
- [ ] All 10 checks PASS (✅)
- [ ] Review any warnings carefully
- [ ] Resolve any failures before proceeding

### Monitoring Setup
- [ ] Application logs configured
- [ ] Error tracking enabled (Sentry/New Relic)
- [ ] Database monitoring ready
- [ ] Redis monitoring ready
- [ ] Uptime monitoring configured

---

## 🚀 DEPLOYMENT PHASE (Execute in Order)

### Step 1: Database Migration
- [ ] Take database backup: `pg_dump $DATABASE_URL > backup_pre_migration.sql`
- [ ] Run migration script:
  ```bash
  psql $DATABASE_URL < migration_production_v1.sql
  ```
- [ ] Verify migration completed without errors
- [ ] Check tables created:
  ```bash
  psql $DATABASE_URL -c "SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema='public';"
  ```
- [ ] Expected: ~45+ tables (system + custom)
- [ ] Verify `shop_profiles` has `gst_number` column:
  ```bash
  psql $DATABASE_URL -c "SELECT column_name FROM information_schema.columns WHERE table_name='shop_profiles' AND column_name='gst_number';"
  ```

### Step 2: Repository Update
- [ ] Pull latest code: `git pull origin main`
- [ ] Check git status: `git status` (should be clean)
- [ ] Verify version in `app.py` is correct
- [ ] No uncommitted changes

### Step 3: Dependency Installation
- [ ] Install/update dependencies: `pip install --upgrade -r requirements.txt`
- [ ] Verify installation: `pip list | grep -E "fastapi|sqlalchemy|redis"`
- [ ] Check for any warnings or errors

### Step 4: Render/Railway Deployment
- [ ] Environment variables set in dashboard
- [ ] Build command configured correctly
- [ ] Start command configured correctly
- [ ] Deploy from Git: `git push origin main`
- [ ] Wait for build to complete (5-10 minutes)
- [ ] Check deployment status

### Step 5: Health Checks
- [ ] App is running (no errors in logs)
- [ ] Health endpoint responds: `curl $API_URL/health`
- [ ] API docs accessible: `curl $API_URL/docs`
- [ ] Database connected successfully
- [ ] Redis connected successfully
- [ ] View logs: `railway logs` or `render logs`

### Step 6: Endpoint Testing
- [ ] Test root endpoint: `curl $API_URL/`
- [ ] Test health: `curl $API_URL/health`
- [ ] Test auth endpoint: `curl -X POST $API_URL/auth/register -H "Content-Type: application/json" -d '{"email":"test@test.com","password":"Test123!"}'`
- [ ] Test inventory endpoint
- [ ] Test invoices endpoint
- [ ] At least 10 different endpoints tested
- [ ] All return proper responses (200/201 for success)

---

## ✅ POST-DEPLOYMENT PHASE (After Going Live)

### Monitoring (First 24 Hours)
- [ ] Monitor error logs in real-time
- [ ] Check error rate (should be <1%)
- [ ] Monitor response times (should be <500ms average)
- [ ] Monitor database connection pool
- [ ] Monitor Redis cache hit rate
- [ ] Check CPU and memory usage
- [ ] Verify no 500 errors in logs

### Functionality Testing
- [ ] Create new user account (Register)
- [ ] Login with credentials (Auth)
- [ ] Create shop profile (Shop Management)
- [ ] Add product (Inventory)
- [ ] Create invoice (Invoicing)
- [ ] Create customer entry (Customer Management)
- [ ] Track attendance (HR)
- [ ] Check khata ledger (Ledger)
- [ ] Test batch operations (if applicable)
- [ ] Test caching system

### Mobile App Testing (If Applicable)
- [ ] Mobile app connects to new API
- [ ] Mobile app can login successfully
- [ ] Mobile app displays shop data correctly
- [ ] Offline sync works
- [ ] All mobile features functional
- [ ] No connection errors in mobile logs

### Integration Testing
- [ ] Email notifications sending successfully
- [ ] QR codes generating correctly
- [ ] PDF exports working
- [ ] Excel exports working
- [ ] SMS/OTP working (if configured)
- [ ] Payment gateway integration (if applicable)
- [ ] All third-party integrations functional

### Performance Testing
- [ ] Load test endpoints (100 requests/minute)
- [ ] Response times acceptable under load
- [ ] Database queries running efficiently
- [ ] No query timeouts
- [ ] Cache effectiveness verified

### Security Audit
- [ ] HTTPS enforced (no HTTP)
- [ ] JWT tokens working correctly
- [ ] Rate limiting active
- [ ] CORS properly configured
- [ ] SQL injection protected
- [ ] XSS protection active
- [ ] No credentials in logs
- [ ] Audit logs recording changes

---

## 🔄 BACKUP & RECOVERY

### Backup Verification
- [ ] Database backup created successfully
- [ ] Backup size is reasonable (~10-100MB)
- [ ] Backup can be restored (test on staging)
- [ ] Automated daily backups configured
- [ ] Backup retention policy set (30 days minimum)

### Disaster Recovery Plan
- [ ] Recovery procedure documented
- [ ] Team trained on recovery steps
- [ ] Recovery time objective (RTO) defined: ___ minutes
- [ ] Recovery point objective (RPO) defined: ___ minutes
- [ ] Failover tested (if applicable)

---

## 📊 MONITORING DASHBOARD

### Key Metrics to Monitor
- [ ] Error Rate: Target <0.1%
- [ ] Response Time: Target <500ms (avg)
- [ ] Database Connections: Target <20 active
- [ ] Cache Hit Rate: Target >70%
- [ ] Uptime: Target 99.9%

### Alerts to Configure
- [ ] Error rate exceeds 1%
- [ ] Response time exceeds 1 second
- [ ] Database connections exceed 25
- [ ] Redis connection lost
- [ ] Disk space low (<10% free)
- [ ] Memory usage >90%

---

## 📱 MOBILE APP SYNC

### If Using Mobile App
- [ ] Flutter/React Native app updated to new API URL
- [ ] Mobile app tested thoroughly
- [ ] Offline sync tested
- [ ] App version bumped
- [ ] App published to stores (if applicable)
- [ ] Users notified of update

---

## 🎯 TEAM COMMUNICATION

### Notify Stakeholders
- [ ] Deployment completed notification sent
- [ ] Team trained on new features
- [ ] Support team briefed on changes
- [ ] Documentation updated
- [ ] Runbook updated
- [ ] Known issues documented

### Customer Communication (If Applicable)
- [ ] Users notified of deployment
- [ ] New features communicated
- [ ] Any downtime communicated in advance
- [ ] Support contact info shared
- [ ] FAQ updated

---

## ⏰ ROLLBACK PLAN (Just In Case)

### If Critical Issues Found
- [ ] Identify critical issue
- [ ] Document the issue
- [ ] Assess rollback necessity
- [ ] Create rollback branch
- [ ] Rollback database (from backup)
- [ ] Redeploy previous stable version
- [ ] Test critical functionality
- [ ] Notify stakeholders
- [ ] Post-mortem meeting scheduled

### Rollback Steps
```bash
# 1. Switch to previous stable version
git checkout v3.0.0  # or previous stable commit

# 2. Restore database from backup
psql $DATABASE_URL < backup_pre_migration.sql

# 3. Redeploy
git push origin main -f

# 4. Verify
curl $API_URL/health
```

---

## ✨ SUCCESS CRITERIA

### Deployment is Successful When:
- [x] All 10 pre-deployment validation checks pass
- [x] Database migration completes without errors
- [x] App starts without errors
- [x] All 100+ endpoints are accessible (HTTP 200)
- [x] Authentication working (JWT tokens issued)
- [x] Database queries returning correct data
- [x] Redis cache working
- [x] Error rate <0.1%
- [x] Response times normal (<500ms average)
- [x] No critical errors in logs
- [x] Mobile app connects successfully (if applicable)
- [x] Team confirms functionality working

---

## 📝 NOTES & OBSERVATIONS

### During Deployment
```
[Note space for observations during deployment]

Time Started: _____________
Time Completed: _____________
Issues Encountered: 

Resolutions Applied:

```

### Post-Deployment Notes
```
[Space for post-deployment observations]

Performance Observations:

Security Observations:

User Feedback:

Recommendations for Next Release:

```

---

## 👥 SIGN-OFF

### Deployment Team
- [ ] Backend Engineer: _____________ (Signature)
- [ ] DevOps Engineer: _____________ (Signature)
- [ ] QA Engineer: _____________ (Signature)
- [ ] Project Manager: _____________ (Signature)

### Approvals
- [ ] Tech Lead Approval
- [ ] Product Manager Approval
- [ ] Security Review Approval

---

## 📞 EMERGENCY CONTACTS

| Role | Name | Phone | Email |
|------|------|-------|-------|
| On-Call Engineer | | | |
| DevOps Lead | | | |
| Database Admin | | | |
| Support Manager | | | |

---

## 📚 DOCUMENTATION LINKS

- [ ] API Documentation: `/docs`
- [ ] Deployment Guide: `DEPLOYMENT_GUIDE.md`
- [ ] Troubleshooting: `DEPLOYMENT_GUIDE.md#troubleshooting`
- [ ] Runbook: [Link to runbook]
- [ ] Architecture Diagram: [Link to diagram]

---

## 🎉 DEPLOYMENT COMPLETE!

**Deployment Status:** ✅ SUCCESSFUL  
**Go-Live Date:** ___________  
**Version Deployed:** 3.0.0  
**Environment:** Production  

**The AI Shop Pro v3.0.0 is now live and ready for 100 crore startup operations!**

---

*Last Updated: 2026-06-18*  
*Checklist Version: 1.0*  
*For Questions: Support Team*
