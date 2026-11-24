from flask import Blueprint, Response, current_app, jsonify, request

from app.business import DomainIssue
from app.evidence.render import artifact, release_artifact
from app.inputs import read_input
from app.modules.pipeline import run
from app.release.service import publish, trial
from app.review.service import execute, review

api = Blueprint("api", __name__, url_prefix="/api")
STAGES = {"intake": 1, "prepare": 2, "calculate": 3, "policy": 4, "balance": 5}


@api.post("/stages/<stage>")
def preview(stage):
    if stage not in STAGES:
        raise DomainIssue("STAGE_UNKNOWN")
    return jsonify(run(read_input(), STAGES[stage]))


@api.route("/runs", methods=["GET", "POST"])
def runs():
    store = current_app.extensions["runs"]
    if request.method == "GET":
        return jsonify(items=store.list())
    return jsonify(execute(store, read_input()))


@api.route("/runs/<run_id>", methods=["GET", "PATCH"])
def batch(run_id):
    store = current_app.extensions["runs"]
    if request.method == "GET":
        return jsonify(store.load(run_id))
    return jsonify(review(store, run_id, request.get_json(silent=True)))


@api.get("/runs/<run_id>/evidence")
def export(run_id):
    report = current_app.extensions["runs"].load(run_id)
    return Response(
        artifact(report),
        mimetype="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="review-{report["id"][:12]}.json"',
            "Cache-Control": "no-store",
        },
    )


@api.post("/releases/trial")
def release_trial():
    store = current_app.extensions["runs"]
    outcome = trial(store, read_input())
    return jsonify({key: value for key, value in outcome.items() if key != "records"})


@api.route("/releases", methods=["GET", "POST"])
def releases():
    store = current_app.extensions["runs"]
    if request.method == "GET":
        return jsonify(items=store.list_releases())
    return jsonify(publish(store, read_input(), request.form.get("expected")))


@api.get("/releases/<release_id>")
def release_detail(release_id):
    return jsonify(current_app.extensions["runs"].load_release(release_id))


@api.get("/releases/<release_id>/evidence")
def release_export(release_id):
    release = current_app.extensions["runs"].load_release(release_id)
    return Response(
        release_artifact(release),
        mimetype="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="release-{release["seq"]}.json"',
            "Cache-Control": "no-store",
        },
    )
