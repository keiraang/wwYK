"""
app.py — Flask application for "What Would YOU Know?"
"""

import json
from flask import Flask, render_template, request, redirect, url_for, session, flash

import database as db
import scoring

app = Flask(__name__)
app.secret_key = "wwyk-secret-change-me"

db.init_db()


# ---------------------------------------------------------------------------
# Context processor — inject current user into every template
# ---------------------------------------------------------------------------

@app.context_processor
def inject_current_user():
    uid = session.get("user_id")
    user = db.get_user(uid) if uid else None
    return {"current_user": user}


# ---------------------------------------------------------------------------
# Select user (no real auth — just pick your name)
# ---------------------------------------------------------------------------

@app.route("/select-user", methods=["GET", "POST"])
def select_user():
    users = db.get_all_users()
    if request.method == "POST":
        uid = int(request.form["user_id"])
        session["user_id"] = uid
        return redirect(url_for("home"))
    return render_template("select_user.html", users=users)


# ---------------------------------------------------------------------------
# Home page
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    if not session.get("user_id"):
        return redirect(url_for("select_user"))
    users = db.get_all_users()
    # Attach level title to each user
    users_with_level = []
    for u in users:
        users_with_level.append({
            "id": u["id"],
            "name": u["name"],
            "xp": u["xp"],
            "points": u["points"],
            "level": scoring.level_title(u["xp"]),
        })
    return render_template("home.html", users=users_with_level)


# ---------------------------------------------------------------------------
# Stats page
# ---------------------------------------------------------------------------

@app.route("/stats/<int:user_id>")
def stats(user_id):
    if not session.get("user_id"):
        return redirect(url_for("select_user"))
    user = db.get_user(user_id)
    if not user:
        flash("User not found.")
        return redirect(url_for("home"))
    skills = db.get_skills(user_id)
    challenges = db.get_challenges_for_user(user_id)
    xp_log = db.get_xp_log(user_id)
    points_log = db.get_points_log(user_id)
    floor, next_thresh = scoring.xp_to_next_level(user["xp"])
    progress_pct = 0
    if next_thresh:
        progress_pct = int((user["xp"] - floor) / (next_thresh - floor) * 100)
    else:
        progress_pct = 100
    return render_template(
        "stats.html",
        profile=user,
        skills=skills,
        challenges=challenges,
        xp_log=xp_log,
        points_log=points_log,
        level=scoring.level_title(user["xp"]),
        progress_pct=progress_pct,
        next_thresh=next_thresh,
    )


# ---------------------------------------------------------------------------
# Add skill
# ---------------------------------------------------------------------------

@app.route("/add-skill", methods=["GET", "POST"])
def add_skill():
    if not session.get("user_id"):
        return redirect(url_for("select_user"))
    if request.method == "POST":
        name = request.form["name"].strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("Skill name is required.")
            return redirect(url_for("add_skill"))
        uid = session["user_id"]
        xp_gain = scoring.xp_for_adding_skill()
        db.add_skill(uid, name, description, xp_gain)
        db.apply_xp(uid, xp_gain, f"Added skill: {name}")
        flash(f'Skill "{name}" added! +{xp_gain} XP')
        return redirect(url_for("stats", user_id=uid))
    return render_template("add_skill.html", xp_gain=scoring.xp_for_adding_skill())


# ---------------------------------------------------------------------------
# Challenge — setup
# ---------------------------------------------------------------------------

@app.route("/challenge/new", methods=["GET", "POST"])
def new_challenge():
    if not session.get("user_id"):
        return redirect(url_for("select_user"))
    users = [u for u in db.get_all_users() if u["id"] != session["user_id"]]
    if request.method == "POST":
        opponent_id = int(request.form["opponent_id"])
        skill_name = request.form["skill_name"].strip()
        challenge_type = request.form["challenge_type"]
        format_ = request.form.get("format", "quiz").strip()
        stakes_desc = request.form.get("stakes_desc", "").strip()
        stakes_points = int(request.form.get("stakes_points", 0))
        scheduled_at = request.form.get("scheduled_at", "").strip() or None

        if not skill_name:
            flash("Please enter a skill name.")
            return redirect(url_for("new_challenge"))

        cid = db.create_challenge(
            challenger_id=session["user_id"],
            opponent_id=opponent_id,
            skill_name=skill_name,
            challenge_type=challenge_type,
            format_=format_,
            stakes_desc=stakes_desc,
            stakes_points=stakes_points,
            scheduled_at=scheduled_at,
        )
        flash("Challenge created!")
        return redirect(url_for("challenge_detail", challenge_id=cid))
    return render_template("new_challenge.html", users=users)


# ---------------------------------------------------------------------------
# Challenge — detail & resolve
# ---------------------------------------------------------------------------

@app.route("/challenge/<int:challenge_id>")
def challenge_detail(challenge_id):
    if not session.get("user_id"):
        return redirect(url_for("select_user"))
    challenge = db.get_challenge(challenge_id)
    if not challenge:
        flash("Challenge not found.")
        return redirect(url_for("home"))
    challenger = db.get_user(challenge["challenger_id"])
    opponent = db.get_user(challenge["opponent_id"])
    result = json.loads(challenge["result"]) if challenge["result"] else None
    return render_template(
        "challenge_detail.html",
        challenge=challenge,
        challenger=challenger,
        opponent=opponent,
        result=result,
        threshold=scoring.NEITHER_PASS_THRESHOLD,
    )


@app.route("/challenge/<int:challenge_id>/resolve", methods=["POST"])
def resolve_challenge(challenge_id):
    if not session.get("user_id"):
        return redirect(url_for("select_user"))
    challenge = db.get_challenge(challenge_id)
    if not challenge or challenge["status"] == "completed":
        flash("Challenge already resolved or not found.")
        return redirect(url_for("home"))

    ctype = challenge["challenge_type"]
    stakes_points = challenge["stakes_points"]
    challenger_id = challenge["challenger_id"]
    opponent_id = challenge["opponent_id"]

    if ctype == "neither_knows":
        # Both players have scores
        challenger_score = int(request.form.get("challenger_score", 0))
        opponent_score = int(request.form.get("opponent_score", 0))
        threshold = scoring.NEITHER_PASS_THRESHOLD

        c_passed = challenger_score >= threshold
        o_passed = opponent_score >= threshold

        c_xp = scoring.xp_for_challenge_result("neither_knows", "challenger", c_passed)
        o_xp = scoring.xp_for_challenge_result("neither_knows", "opponent", o_passed)

        db.apply_xp(challenger_id, c_xp, f"Challenge (neither knows): {challenge['skill_name']}")
        db.apply_xp(opponent_id, o_xp, f"Challenge (neither knows): {challenge['skill_name']}")

        # Points: whoever scored higher wins
        if challenger_score > opponent_score:
            db.apply_points(challenger_id, scoring.points_for_challenge(True, stakes_points),
                            f"Won challenge: {challenge['skill_name']}")
            db.apply_points(opponent_id, scoring.points_for_challenge(False, stakes_points),
                            f"Lost challenge: {challenge['skill_name']}")
            winner = "challenger"
        elif opponent_score > challenger_score:
            db.apply_points(opponent_id, scoring.points_for_challenge(True, stakes_points),
                            f"Won challenge: {challenge['skill_name']}")
            db.apply_points(challenger_id, scoring.points_for_challenge(False, stakes_points),
                            f"Lost challenge: {challenge['skill_name']}")
            winner = "opponent"
        else:
            winner = "tie"

        result = {
            "winner": winner,
            "challenger_score": challenger_score,
            "opponent_score": opponent_score,
        }
    else:
        # opponent_passed = True means opponent successfully demonstrated the skill
        opponent_passed = request.form.get("outcome") == "opponent_passed"

        c_xp = scoring.xp_for_challenge_result(ctype, "challenger", opponent_passed)
        o_xp = scoring.xp_for_challenge_result(ctype, "opponent", opponent_passed)

        db.apply_xp(challenger_id, c_xp, f"Challenge ({ctype}): {challenge['skill_name']}")
        db.apply_xp(opponent_id, o_xp, f"Challenge ({ctype}): {challenge['skill_name']}")

        # Points: challenger wins if opponent failed; opponent wins if they passed
        if opponent_passed:
            db.apply_points(opponent_id, scoring.points_for_challenge(True, stakes_points),
                            f"Won challenge: {challenge['skill_name']}")
            db.apply_points(challenger_id, scoring.points_for_challenge(False, stakes_points),
                            f"Lost challenge: {challenge['skill_name']}")
            winner = "opponent"
        else:
            db.apply_points(challenger_id, scoring.points_for_challenge(True, stakes_points),
                            f"Won challenge: {challenge['skill_name']}")
            db.apply_points(opponent_id, scoring.points_for_challenge(False, stakes_points),
                            f"Lost challenge: {challenge['skill_name']}")
            winner = "challenger"

        result = {"winner": winner, "opponent_passed": opponent_passed}

    db.complete_challenge(challenge_id, json.dumps(result))
    flash("Challenge resolved!")
    return redirect(url_for("challenge_detail", challenge_id=challenge_id))


# ---------------------------------------------------------------------------
# Refresher
# ---------------------------------------------------------------------------

@app.route("/refresher", methods=["GET", "POST"])
def refresher():
    if not session.get("user_id"):
        return redirect(url_for("select_user"))
    uid = session["user_id"]
    skills = db.get_skills(uid)
    if request.method == "POST":
        skill_name = request.form["skill_name"]
        passed = request.form.get("passed") == "yes"
        delta = scoring.xp_for_refresher(passed)
        db.apply_xp(uid, delta, f"Refresher ({'pass' if passed else 'fail'}): {skill_name}")
        if passed:
            flash(f"Refresher passed! +{delta} XP")
        else:
            flash(f"Refresher failed. {delta} XP")
        return redirect(url_for("stats", user_id=uid))
    return render_template("refresher.html", skills=skills)


if __name__ == "__main__":
    # Port 5000 is reserved by AirPlay on macOS — use 5001
    app.run(debug=True, port=5001)
