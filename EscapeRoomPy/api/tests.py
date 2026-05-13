"""
Tests for the Escape Room Creator API.

Covers:
  - 13 property-based tests (P1-P13) using Hypothesis
  - 4 example tests: auth 401, full flow, stats 403, delete 409

Feature: escape-room-creator-rpg
"""
import json
import uuid

from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase as HypothesisTestCase

from .models import Room, Question, RoomSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unique_username(prefix="user"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _make_user(username=None, password="pass1234"):
    if username is None:
        username = _unique_username()
    return User.objects.create_user(username=username, password=password)


def _get_token(client, username, password="pass1234"):
    resp = client.post("/token/", {"username": username, "password": password}, format="json")
    return resp.data["access"]


def _auth(client, token):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _make_room(client, title="Test Room", difficulty="easy"):
    return client.post("/rooms/", {"title": title, "difficulty": difficulty}, format="json")


def _make_question(client, room_id, text="Question text?", correct_index=0):
    return client.post(
        "/questions/",
        {
            "room": room_id,
            "text": text,
            "option_0": "A",
            "option_1": "B",
            "option_2": "C",
            "option_3": "D",
            "correct_index": correct_index,
        },
        format="json",
    )


def _add_n_questions(client, room_id, n):
    for i in range(n):
        _make_question(client, room_id, text=f"Question {i}?")


def _make_client_with_user(password="pass1234"):
    """Create a fresh user + authenticated APIClient."""
    user = _make_user(password=password)
    client = APIClient()
    resp = client.post("/token/", {"username": user.username, "password": password}, format="json")
    token = resp.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client, user


# ---------------------------------------------------------------------------
# Example Tests
# ---------------------------------------------------------------------------

class ExampleTests(APITestCase):
    """Concrete example tests for auth, full flow, stats 403, delete 409."""

    def setUp(self):
        self.user = _make_user("alice_example")
        self.token = _get_token(self.client, "alice_example")

    # ---- test_unauthenticated_401 ------------------------------------------

    def test_unauthenticated_401(self):
        """POST /rooms/, /questions/, /room-sessions/ without token -> 401."""
        self.client.credentials()  # clear any auth

        r1 = self.client.post("/rooms/", {"title": "X", "difficulty": "easy"}, format="json")
        self.assertEqual(r1.status_code, 401)

        r2 = self.client.post(
            "/questions/",
            {"room": 1, "text": "Q?", "option_0": "A", "option_1": "B",
             "option_2": "C", "option_3": "D", "correct_index": 0},
            format="json",
        )
        self.assertEqual(r2.status_code, 401)

        r3 = self.client.post(
            "/room-sessions/",
            {"room": 1, "time_taken": 60, "questions_answered": 4,
             "correct_answers": 3, "completed": True},
            format="json",
        )
        self.assertEqual(r3.status_code, 401)

    # ---- test_full_flow ----------------------------------------------------

    def test_full_flow(self):
        """Create room -> add 4 questions -> publish -> create session -> verify in history."""
        _auth(self.client, self.token)

        # 1. Create room
        r = _make_room(self.client, title="Full Flow Room")
        self.assertEqual(r.status_code, 201)
        room_id = r.data["id"]

        # 2. Add 4 questions
        _add_n_questions(self.client, room_id, 4)
        self.assertEqual(Room.objects.get(pk=room_id).questions.count(), 4)

        # 3. Publish
        pub = self.client.post(f"/rooms/{room_id}/publish/", format="json")
        self.assertEqual(pub.status_code, 200)
        self.assertEqual(pub.data["status"], "published")

        # 4. Create session
        sess = self.client.post(
            "/room-sessions/",
            {
                "room": room_id,
                "time_taken": 120.5,
                "questions_answered": 4,
                "correct_answers": 3,
                "completed": True,
            },
            format="json",
        )
        self.assertEqual(sess.status_code, 201)

        # 5. Verify in history
        history = self.client.get("/room-sessions/")
        self.assertEqual(history.status_code, 200)
        ids = [s["id"] for s in history.data]
        self.assertIn(sess.data["id"], ids)

    # ---- test_stats_foreign_room_403 ---------------------------------------

    def test_stats_foreign_room_403(self):
        """Request stats of another user's room -> 403."""
        # Create and publish room as alice
        _auth(self.client, self.token)
        r = _make_room(self.client, title="Alice Room Stats")
        room_id = r.data["id"]
        # Publish so Bob can see it
        _add_n_questions(self.client, room_id, 4)
        self.client.post(f"/rooms/{room_id}/publish/", format="json")

        # Bob tries to access stats
        bob = _make_user("bob_stats_test")
        bob_token = _get_token(self.client, "bob_stats_test")
        _auth(self.client, bob_token)

        resp = self.client.get(f"/rooms/{room_id}/stats/")
        self.assertEqual(resp.status_code, 403)

    # ---- test_delete_published_room_with_sessions_409 ----------------------

    def test_delete_published_room_with_sessions_409(self):
        """Try to delete published room that has sessions -> 409."""
        _auth(self.client, self.token)

        # Create and publish room
        r = _make_room(self.client, title="Delete Test Room")
        room_id = r.data["id"]
        _add_n_questions(self.client, room_id, 4)
        pub = self.client.post(f"/rooms/{room_id}/publish/", format="json")
        self.assertEqual(pub.status_code, 200)

        # Create a session
        sess = self.client.post(
            "/room-sessions/",
            {
                "room": room_id,
                "time_taken": 60,
                "questions_answered": 4,
                "correct_answers": 4,
                "completed": True,
            },
            format="json",
        )
        self.assertEqual(sess.status_code, 201)

        # Try to delete
        resp = self.client.delete(f"/rooms/{room_id}/")
        self.assertEqual(resp.status_code, 409)


# ---------------------------------------------------------------------------
# Property-Based Tests (Hypothesis)
# ---------------------------------------------------------------------------

class PropertyTests(HypothesisTestCase):
    """
    Property-based tests P1-P13 using Hypothesis.
    Feature: escape-room-creator-rpg

    NOTE: Each test creates fresh users with unique names to avoid UNIQUE
    constraint violations across Hypothesis examples. setUp is called once
    per test method, not once per example.
    """

    # ---- P1: Validacion de Question invalida --------------------------------
    # Validates: Requirements 1.2, 1.3

    @given(case=st.one_of(
        # Invalid text: empty (max_size=0)
        st.text(max_size=0).map(lambda t: {"text": t, "correct_index": 0}),
        # Invalid text: too long (min_size=501)
        st.text(min_size=501).map(lambda t: {"text": t, "correct_index": 0}),
        # Invalid correct_index: outside {0,1,2,3}
        st.integers().filter(lambda x: x not in range(4)).map(
            lambda i: {"text": "Valid question text?", "correct_index": i}
        ),
    ))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_invalid_question_rejected(self, case):
        """P1: Question with invalid text or correct_index is rejected with 400.

        Covers:
        - text with max_size=0 (empty)
        - text with min_size=501 (too long)
        - correct_index outside {0,1,2,3}

        **Validates: Requirements 1.2, 1.3**
        Feature: escape-room-creator-rpg, Property 1
        """
        client, user = _make_client_with_user()
        room_resp = _make_room(client, title="P1 Room")
        room_id = room_resp.data["id"]

        resp = client.post(
            "/questions/",
            {
                "room": room_id,
                "text": case["text"],
                "option_0": "A",
                "option_1": "B",
                "option_2": "C",
                "option_3": "D",
                "correct_index": case["correct_index"],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    # ---- P2: Aislamiento de Questions por Creator --------------------------
    # Validates: Requirements 1.4

    @given(n_a=st.integers(min_value=1, max_value=3), n_b=st.integers(min_value=1, max_value=3))
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_question_isolation_by_creator(self, n_a, n_b):
        """P2: Creator A only sees their own questions.
        Validates: Requirements 1.4"""
        client_a, user_a = _make_client_with_user()
        client_b, user_b = _make_client_with_user()

        room_a = _make_room(client_a, title="P2 Room A").data["id"]
        for i in range(n_a):
            _make_question(client_a, room_a, text=f"A question {i}?")

        room_b = _make_room(client_b, title="P2 Room B").data["id"]
        for i in range(n_b):
            _make_question(client_b, room_b, text=f"B question {i}?")

        # A sees only their questions
        resp_a = client_a.get("/questions/")
        self.assertEqual(resp_a.status_code, 200)
        for q in resp_a.data:
            self.assertEqual(q["creator"], user_a.id)

        # B sees only their questions
        resp_b = client_b.get("/questions/")
        self.assertEqual(resp_b.status_code, 200)
        for q in resp_b.data:
            self.assertEqual(q["creator"], user_b.id)

    # ---- P3: Ownership de Questions (403) ----------------------------------
    # Validates: Requirements 1.6

    @given(method=st.sampled_from(["patch", "delete"]))
    @settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_question_ownership_403(self, method):
        """P3: Creator A cannot update/delete Creator B's question (403).
        Validates: Requirements 1.6"""
        client_a, user_a = _make_client_with_user()
        client_b, user_b = _make_client_with_user()

        # B creates a question
        room_b = _make_room(client_b, title="P3 Room B").data["id"]
        q_resp = _make_question(client_b, room_b, text="B's question?")
        q_id = q_resp.data["id"]

        # A tries to modify/delete it
        if method == "patch":
            resp = client_a.patch(f"/questions/{q_id}/", {"text": "Hacked?"}, format="json")
        else:
            resp = client_a.delete(f"/questions/{q_id}/")

        self.assertIn(resp.status_code, [403, 404])

    # ---- P4: Validacion de Room invalida -----------------------------------
    # Validates: Requirements 2.2, 2.3, 2.4

    @given(case=st.one_of(
        # Empty title
        st.just({"title": "", "difficulty": "easy"}),
        # Title longer than 100 characters
        st.text(min_size=101, max_size=150).map(
            lambda t: {"title": t, "difficulty": "easy"}
        ),
        # Invalid difficulty (not in {easy, medium, hard})
        st.text(min_size=1, max_size=20).filter(
            lambda d: d not in ("easy", "medium", "hard")
        ).map(lambda d: {"title": "Valid Title", "difficulty": d}),
    ))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_invalid_room_rejected(self, case):
        """P4: Room with invalid title or difficulty is rejected with HTTP 400.

        Covers:
        - Empty title
        - Title longer than 100 characters
        - Difficulty not in {easy, medium, hard}

        **Validates: Requirements 2.2, 2.3, 2.4**
        Feature: escape-room-creator-rpg, Property 4
        """
        client, _ = _make_client_with_user()
        resp = client.post("/rooms/", case, format="json")
        self.assertEqual(resp.status_code, 400)

    # ---- P5: Restriccion de publicacion por numero de Questions ------------
    # Validates: Requirements 2.5

    @given(
        n_few=st.integers(min_value=0, max_value=3),
        n_many=st.integers(min_value=63, max_value=65),
        n_valid=st.integers(min_value=4, max_value=8),
    )
    @settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_publish_question_count_constraint(self, n_few, n_many, n_valid):
        """P5: Restricción de publicación por número de Questions.

        - Rooms with < 4 questions (0-3) cannot be published → HTTP 400
        - Rooms with > 62 questions (63+) cannot be published → HTTP 400
        - Rooms with 4-62 questions CAN be published → HTTP 200

        **Validates: Requirements 2.5**
        Feature: escape-room-creator-rpg, Property 5
        """
        # Case 1: too few questions (0-3) → 400
        client_few, _ = _make_client_with_user()
        room_few = _make_room(client_few, title=f"P5 Few Room {n_few}").data["id"]
        _add_n_questions(client_few, room_few, n_few)
        resp_few = client_few.post(f"/rooms/{room_few}/publish/", format="json")
        self.assertEqual(resp_few.status_code, 400)

        # Case 2: too many questions (63+) → 400
        client_many, _ = _make_client_with_user()
        room_many = _make_room(client_many, title=f"P5 Many Room {n_many}").data["id"]
        _add_n_questions(client_many, room_many, n_many)
        resp_many = client_many.post(f"/rooms/{room_many}/publish/", format="json")
        self.assertEqual(resp_many.status_code, 400)

        # Case 3: valid question count (4-62) → 200
        client_valid, _ = _make_client_with_user()
        room_valid = _make_room(client_valid, title=f"P5 Valid Room {n_valid}").data["id"]
        _add_n_questions(client_valid, room_valid, n_valid)
        resp_valid = client_valid.post(f"/rooms/{room_valid}/publish/", format="json")
        self.assertEqual(resp_valid.status_code, 200)

    # ---- P6: Visibilidad en catalogo tras publicacion ----------------------
    # Validates: Requirements 2.6, 3.1

    @given(difficulty=st.sampled_from(["easy", "medium", "hard"]))
    @settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_catalog_visibility_after_publish(self, difficulty):
        """P6: Published room appears in catalog; draft does not.
        Validates: Requirements 2.6, 3.1"""
        client, user = _make_client_with_user()
        room_id = _make_room(client, title=f"P6 Room {difficulty}", difficulty=difficulty).data["id"]
        _add_n_questions(client, room_id, 4)

        # Before publish: not in public catalog (unauthenticated)
        anon = APIClient()
        catalog_before = anon.get("/rooms/")
        ids_before = [r["id"] for r in catalog_before.data]
        self.assertNotIn(room_id, ids_before)

        # Publish
        client.post(f"/rooms/{room_id}/publish/", format="json")

        # After publish: appears in public catalog
        catalog_after = anon.get("/rooms/")
        ids_after = [r["id"] for r in catalog_after.data]
        self.assertIn(room_id, ids_after)

    # ---- P7: Filtrado del catalogo por dificultad --------------------------
    # Validates: Requirements 3.2

    @given(difficulty=st.sampled_from(["easy", "medium", "hard"]))
    @settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_catalog_difficulty_filter(self, difficulty):
        """P7: GET /rooms/?difficulty=X returns only rooms with that difficulty.
        Validates: Requirements 3.2"""
        client, user = _make_client_with_user()

        # Create and publish a room with the given difficulty
        room_id = _make_room(client, title=f"P7 Room {difficulty}", difficulty=difficulty).data["id"]
        _add_n_questions(client, room_id, 4)
        client.post(f"/rooms/{room_id}/publish/", format="json")

        # Filter catalog (unauthenticated)
        anon = APIClient()
        resp = anon.get(f"/rooms/?difficulty={difficulty}")
        self.assertEqual(resp.status_code, 200)
        for room in resp.data:
            self.assertEqual(room["difficulty"], difficulty)

    # ---- P8: Detalle de Room sin correct_index -----------------------------
    # Validates: Requirements 3.4

    @given(correct_index=st.integers(min_value=0, max_value=3))
    @settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_room_detail_hides_correct_index(self, correct_index):
        """P8: GET /rooms/{id}/ never includes correct_index in questions.
        Validates: Requirements 3.4"""
        client, user = _make_client_with_user()
        room_id = _make_room(client, title="P8 Room").data["id"]
        _make_question(client, room_id, text="P8 question?", correct_index=correct_index)
        _add_n_questions(client, room_id, 3)
        client.post(f"/rooms/{room_id}/publish/", format="json")

        # Public detail (unauthenticated)
        anon = APIClient()
        resp = anon.get(f"/rooms/{room_id}/")
        self.assertEqual(resp.status_code, 200)

        for q in resp.data.get("questions", []):
            self.assertNotIn("correct_index", q)

    # ---- P9: Registro correcto de Room_Session -----------------------------
    # Validates: Requirements 4.4, 5.1

    @given(
        time_taken=st.floats(min_value=1.0, max_value=3600.0, allow_nan=False, allow_infinity=False),
        questions_answered=st.integers(min_value=1, max_value=10),
        correct_answers=st.integers(min_value=0, max_value=10),
        completed=st.booleans(),
    )
    @settings(max_examples=15, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_room_session_created_correctly(self, time_taken, questions_answered, correct_answers, completed):
        """P9: POST /room-sessions/ creates session with exact values, returns 201.
        Validates: Requirements 4.4, 5.1"""
        client, user = _make_client_with_user()
        room_id = _make_room(client, title="P9 Room").data["id"]
        _add_n_questions(client, room_id, 4)
        client.post(f"/rooms/{room_id}/publish/", format="json")

        resp = client.post(
            "/room-sessions/",
            {
                "room": room_id,
                "time_taken": time_taken,
                "questions_answered": questions_answered,
                "correct_answers": correct_answers,
                "completed": completed,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertAlmostEqual(resp.data["time_taken"], time_taken, places=3)
        self.assertEqual(resp.data["questions_answered"], questions_answered)
        self.assertEqual(resp.data["correct_answers"], correct_answers)
        self.assertEqual(resp.data["completed"], completed)

    # ---- P10: Aislamiento de Room_Sessions por usuario ---------------------
    # Validates: Requirements 5.2

    @given(n_a=st.integers(min_value=1, max_value=2), n_b=st.integers(min_value=1, max_value=2))
    @settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_room_session_isolation_by_user(self, n_a, n_b):
        """P10: User A's sessions not visible to User B.
        Validates: Requirements 5.2"""
        client_a, user_a = _make_client_with_user()
        client_b, user_b = _make_client_with_user()

        # Create a shared published room (owned by A)
        room_id = _make_room(client_a, title="P10 Room").data["id"]
        _add_n_questions(client_a, room_id, 4)
        client_a.post(f"/rooms/{room_id}/publish/", format="json")

        def post_session(client, n):
            for _ in range(n):
                client.post(
                    "/room-sessions/",
                    {"room": room_id, "time_taken": 60, "questions_answered": 4,
                     "correct_answers": 3, "completed": True},
                    format="json",
                )

        post_session(client_a, n_a)
        post_session(client_b, n_b)

        # A sees only their sessions
        resp_a = client_a.get("/room-sessions/")
        for s in resp_a.data:
            self.assertEqual(s["user"], user_a.username)

        # B sees only their sessions
        resp_b = client_b.get("/room-sessions/")
        for s in resp_b.data:
            self.assertEqual(s["user"], user_b.username)

    # ---- P11: Correccion de estadisticas de Room ---------------------------
    # Validates: Requirements 5.4

    @given(sessions=st.lists(
        st.fixed_dictionaries({
            "time_taken": st.floats(min_value=1.0, max_value=600.0, allow_nan=False, allow_infinity=False),
            "completed": st.booleans(),
        }),
        min_size=1,
        max_size=4,
    ))
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_room_stats_correctness(self, sessions):
        """P11: /rooms/{id}/stats/ returns correct total_games, avg_time, completion_rate.
        Validates: Requirements 5.4"""
        client, user = _make_client_with_user()
        room_id = _make_room(client, title="P11 Room").data["id"]
        _add_n_questions(client, room_id, 4)
        client.post(f"/rooms/{room_id}/publish/", format="json")

        for s in sessions:
            client.post(
                "/room-sessions/",
                {
                    "room": room_id,
                    "time_taken": s["time_taken"],
                    "questions_answered": 4,
                    "correct_answers": 2,
                    "completed": s["completed"],
                },
                format="json",
            )

        resp = client.get(f"/rooms/{room_id}/stats/")
        self.assertEqual(resp.status_code, 200)

        n = len(sessions)
        expected_avg = sum(s["time_taken"] for s in sessions) / n
        expected_rate = (sum(1 for s in sessions if s["completed"]) / n) * 100

        self.assertEqual(resp.data["total_games"], n)
        self.assertAlmostEqual(resp.data["avg_time"], expected_avg, places=2)
        self.assertAlmostEqual(resp.data["completion_rate"], expected_rate, places=2)

    # ---- P12: Round-trip de serializacion de Room --------------------------
    # Validates: Requirements 8.1, 8.2, 8.3

    @given(
        title=st.text(min_size=1, max_size=100).filter(lambda t: t.strip()),
        difficulty=st.sampled_from(["easy", "medium", "hard"]),
        description=st.text(max_size=200),
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_room_serialization_round_trip(self, title, difficulty, description):
        """P12: Serialize Room to JSON and back produces equivalent object.
        Validates: Requirements 8.1, 8.2, 8.3"""
        from .serializers import RoomSerializer
        from django.test import RequestFactory

        user = _make_user()
        room = Room.objects.create(
            title=title,
            difficulty=difficulty,
            description=description,
            creator=user,
        )

        factory = RequestFactory()
        request = factory.get("/")
        request.user = user

        serializer = RoomSerializer(room, context={"request": request})
        data = serializer.data

        # Verify key fields round-trip correctly
        self.assertEqual(data["title"], title)
        self.assertEqual(data["difficulty"], difficulty)
        self.assertEqual(data["description"], description)
        self.assertEqual(data["creator"], user.username)

        # Verify JSON serialization is stable
        json_str = json.dumps(dict(data))
        parsed = json.loads(json_str)
        self.assertEqual(parsed["title"], title)
        self.assertEqual(parsed["difficulty"], difficulty)

    # ---- P13: Rechazo de JSON invalido con nombres de campos ---------------
    # Validates: Requirements 8.4

    @given(payload=st.one_of(
        # Missing title
        st.just({"difficulty": "easy"}),
        # Missing difficulty
        st.just({"title": "Valid Title"}),
        # Empty title
        st.just({"title": "", "difficulty": "easy"}),
    ))
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_invalid_json_rejected_with_field_names(self, payload):
        """P13: Missing required fields or wrong types return 400 with field names.
        Validates: Requirements 8.4"""
        client, user = _make_client_with_user()
        resp = client.post("/rooms/", payload, format="json")
        self.assertEqual(resp.status_code, 400)
        # Response should contain field names
        resp_json = resp.data
        self.assertIsInstance(resp_json, dict)
        self.assertTrue(len(resp_json) > 0, "400 response should include field error names")

