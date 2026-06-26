from app.models import CollectItem, CollectJob, Museum


def test_list_jobs_empty(client):
    resp = client.get("/admin/collect/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


def test_job_detail_not_found(client):
    resp = client.get("/admin/collect/jobs/99999")
    assert resp.status_code == 404


def test_cancel_nonexistent(client):
    resp = client.post("/admin/collect/jobs/99999/cancel")
    assert resp.status_code == 404


def test_admin_museums_list(client, test_db):
    m = Museum(name="测试馆", geo_fence=[], city="北京", country="中国", lat=0.0, lng=0.0)
    test_db.add(m)
    test_db.flush()
    test_db.commit()
    resp = client.get("/admin/museums")
    assert resp.status_code == 200
    names = [x["name"] for x in resp.json()["museums"]]
    assert "测试馆" in names


def test_list_jobs_with_records(client, test_db):
    """直接插 collect_jobs 记录，验证列表返回。"""
    m = Museum(name="X馆", geo_fence=[], city="x", country="x", lat=0.0, lng=0.0)
    test_db.add(m)
    test_db.flush()
    job = CollectJob(museum_id=m.id, source="baike", stage="succeeded",
                     total=10, done=10, failed=0, log=[])
    test_db.add(job)
    test_db.flush()
    test_db.commit()

    resp = client.get("/admin/collect/jobs")
    data = resp.json()
    assert data["total"] >= 1
    j = data["jobs"][0]
    assert j["source"] == "baike"
    assert j["stage"] == "succeeded"
    assert j["museum_name"] == "X馆"


def test_job_detail_with_items(client, test_db):
    """任务详情返回 job + items。"""
    m = Museum(name="Y馆", geo_fence=[], city="x", country="x", lat=0.0, lng=0.0)
    test_db.add(m)
    test_db.flush()
    job = CollectJob(museum_id=m.id, source="wiki", stage="partial",
                     total=2, done=1, failed=1, log=[])
    test_db.add(job)
    test_db.flush()
    test_db.add(CollectItem(job_id=job.id, name="展品A", stage="saved", target_type="exhibit", target_id=1))
    test_db.add(CollectItem(job_id=job.id, name="展品B", stage="failed", target_type="exhibit", error="超时"))
    test_db.flush()
    test_db.commit()

    resp = client.get(f"/admin/collect/jobs/{job.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job"]["stage"] == "partial"
    assert len(data["items"]) == 2
    stages = {i["stage"] for i in data["items"]}
    assert stages == {"saved", "failed"}
