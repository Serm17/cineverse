
from sqlalchemy import select

from app.models.users import UserPreferenceScore
from app.services.user_service import check_unique_values

# 영화.장르 사용자의 장르에 추가
def movie_genre_add_preferences_user(user, movie):
    user.preferred_genres = check_unique_values(user.preferred_genres, movie.genres)

    user.preferred_actors = check_unique_values(user.preferred_actors, movie.cast)

    user.preferred_keywords = check_unique_values(user.preferred_keywords, movie.keywords)


def get_user_preference_scores(db, user_id):
    return list(
        db.scalars(
            select(UserPreferenceScore)
            .where(UserPreferenceScore.user_id == user_id)
            .order_by(UserPreferenceScore.score.desc())
        ).all()
    )