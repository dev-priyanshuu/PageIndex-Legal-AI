from __future__ import annotations


class MemoryAgent:
    """Appends each question/answer pair to the session history."""

    def update(
        self,
        session_questions: list[str],
        session_answers: list[str],
        question: str,
        answer: str,
    ) -> None:
        session_questions.append(question)
        session_answers.append(answer)
