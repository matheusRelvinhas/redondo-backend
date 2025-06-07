import pytz
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()
brasilia_tz = pytz.timezone('America/Sao_Paulo')

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=True)
    access_recover_token = db.Column(db.String(255), nullable=True)
    amount_logins = db.Column(db.Integer, nullable=True, default=0)
    created_at = db.Column(db.Integer, default=lambda: int(datetime.now(brasilia_tz).timestamp()), nullable=True)
    updated_at = db.Column(db.Integer, default=lambda: int(datetime.now(brasilia_tz).timestamp()), onupdate=lambda: int(datetime.now(brasilia_tz).timestamp()), nullable=True)

class TeamsStats(db.Model):
    __tablename__ = 'teams_stats'

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, nullable=False)
    team_name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False)
    points = db.Column(db.Integer, nullable=True)
    rank = db.Column(db.Integer, nullable=True)
    country_name = db.Column(db.String(100), nullable=True)
    country_code = db.Column(db.String(10), nullable=True)
    region_code = db.Column(db.String(10), nullable=True)
    image_url = db.Column(db.String(250), nullable=True)
    team_valve_rankings_players = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.Integer, default=lambda: int(datetime.now(brasilia_tz).timestamp()), nullable=True)
    updated_at = db.Column(db.Integer, default=lambda: int(datetime.now(brasilia_tz).timestamp()), onupdate=lambda: int(datetime.now(brasilia_tz).timestamp()), nullable=True)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class PlayerStatsBase(db.Model):
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    player_id = db.Column(db.Integer, nullable=False)
    nickname = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    country_code = db.Column(db.String(10), nullable=True)
    region_id = db.Column(db.Integer, nullable=True)
    team_id = db.Column(db.Integer, nullable=True)
    total_prize = db.Column(db.Float, nullable=True)
    image_url = db.Column(db.String(250), nullable=True)

    games_count = db.Column(db.Integer, nullable=True)
    rounds_count= db.Column(db.Integer, nullable=True)
    rounds_win= db.Column(db.Integer, nullable=True)

    avg_player_rating_value = db.Column(db.Float, nullable=True)
    avg_player_rating = db.Column(db.Float, nullable=True)
    kills_sum = db.Column(db.Integer, nullable=True)
    avg_kills = db.Column(db.Float, nullable=True)
    death_sum = db.Column(db.Integer, nullable=True)
    avg_death = db.Column(db.Float, nullable=True)
    assists_sum = db.Column(db.Integer, nullable=True)
    avg_assists = db.Column(db.Float, nullable=True)
    damage_sum = db.Column(db.Integer, nullable=True)
    avg_damage = db.Column(db.Float, nullable=True)
    kd_diff_sum = db.Column(db.Integer, nullable=True)
    avg_kd_rate = db.Column(db.Float, nullable=True)
    avg_first_kills = db.Column(db.Float, nullable=True)
    avg_first_death = db.Column(db.Float, nullable=True)
    avg_trade_kills = db.Column(db.Float, nullable=True)
    avg_trade_death = db.Column(db.Float, nullable=True)
    avg_multikills = db.Column(db.Float, nullable=True)
    avg_shots = db.Column(db.Float, nullable=True)
    avg_shots_accuracy = db.Column(db.Float, nullable=True)
    avg_headshots = db.Column(db.Float, nullable=True)
    avg_headshots_accuracy = db.Column(db.Float, nullable=True)
    avg_headshot_kills_accuracy = db.Column(db.Float, nullable=True)
    avg_flash_assists = db.Column(db.Float, nullable=True)
    avg_flash_hits = db.Column(db.Float, nullable=True)
    avg_flash_duration = db.Column(db.Float, nullable=True)
    avg_he_damage = db.Column(db.Float, nullable=True)
    avg_molotov_damage = db.Column(db.Float, nullable=True)
    avg_kill_cost = db.Column(db.Float, nullable=True)
    avg_hundred_damage_cost = db.Column(db.Float, nullable=True)
    avg_saved = db.Column(db.Float, nullable=True)
    avg_multikills_vs_2 = db.Column(db.Float, nullable=True)
    avg_multikills_vs_3 = db.Column(db.Float, nullable=True)
    avg_multikills_vs_4 = db.Column(db.Float, nullable=True)
    avg_multikills_vs_5 = db.Column(db.Float, nullable=True)
    multikills_vs_2 = db.Column(db.Integer, nullable=True)
    multikills_vs_3 = db.Column(db.Integer, nullable=True)
    multikills_vs_4 = db.Column(db.Integer, nullable=True)
    multikills_vs_5 = db.Column(db.Integer, nullable=True)
    avg_clutches_vs_1 = db.Column(db.Float, nullable=True)
    avg_clutches_vs_2 = db.Column(db.Float, nullable=True)
    avg_clutches_vs_3 = db.Column(db.Float, nullable=True)
    avg_clutches_vs_4 = db.Column(db.Float, nullable=True)
    avg_clutches_vs_5 = db.Column(db.Float, nullable=True)
    clutches_vs_1 = db.Column(db.Integer, nullable=True)
    clutches_vs_2 = db.Column(db.Integer, nullable=True)
    clutches_vs_3 = db.Column(db.Integer, nullable=True)
    clutches_vs_4 = db.Column(db.Integer, nullable=True)
    clutches_vs_5 = db.Column(db.Integer, nullable=True)
    avg_ak47_kills = db.Column(db.Float, nullable=True)
    avg_ak47_damage = db.Column(db.Float, nullable=True)
    ak47_shots_accuracy = db.Column(db.Float, nullable=True)
    ak47_headshots_accuracy = db.Column(db.Float, nullable=True)
    avg_m4a4_kills = db.Column(db.Float, nullable=True)
    avg_m4a4_damage = db.Column(db.Float, nullable=True)
    m4a4_shots_accuracy = db.Column(db.Float, nullable=True)
    m4a4_headshots_accuracy = db.Column(db.Float, nullable=True)
    avg_m4a1_kills = db.Column(db.Float, nullable=True)
    avg_m4a1_damage = db.Column(db.Float, nullable=True)
    m4a1_shots_accuracy = db.Column(db.Float, nullable=True)
    m4a1_headshots_accuracy = db.Column(db.Float, nullable=True)
    avg_awp_kills = db.Column(db.Float, nullable=True)
    avg_awp_damage = db.Column(db.Float, nullable=True)
    awp_shots_accuracy =  db.Column(db.Float, nullable=True)
    awp_headshots_accuracy = db.Column(db.Float, nullable=True)
    avg_galil_kills = db.Column(db.Float, nullable=True)
    avg_galil_damage = db.Column(db.Float, nullable=True)
    galil_shots_accuracy = db.Column(db.Float, nullable=True)
    galil_headshots_accuracy = db.Column(db.Float, nullable=True)
    avg_aug_kills = db.Column(db.Float, nullable=True)
    avg_aug_damage = db.Column(db.Float, nullable=True)
    aug_shots_accuracy = db.Column(db.Float, nullable=True)
    aug_headshots_accuracy = db.Column(db.Float, nullable=True)
    avg_desert_eagle_kills = db.Column(db.Float, nullable=True)
    avg_desert_eagle_damage = db.Column(db.Float, nullable=True)
    desert_eagle_shots_accuracy = db.Column(db.Float, nullable=True)
    desert_eagle_headshots_accuracy = db.Column(db.Float, nullable=True)
    avg_usp_s_kills = db.Column(db.Float, nullable=True)
    avg_usp_s_damage = db.Column(db.Float, nullable=True)
    usp_s_shots_accuracy = db.Column(db.Float, nullable=True)
    usp_s_headshots_accuracy = db.Column(db.Float, nullable=True)
    avg_glock_kills = db.Column(db.Float, nullable=True)
    avg_glock_damage = db.Column(db.Float, nullable=True)
    glock_shots_accuracy = db.Column(db.Float, nullable=True)
    glock_headshots_accuracy = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.Integer, default=lambda: int(datetime.now(brasilia_tz).timestamp()), nullable=True)
    updated_at = db.Column(db.Integer, default=lambda: int(datetime.now(brasilia_tz).timestamp()), onupdate=lambda: int(datetime.now(brasilia_tz).timestamp()), nullable=True)

    def to_dict(self):
        exclude_fields = {"player_id", "image_url", "region_id"}
        data = {
            c.name: getattr(self, c.name)
            for c in self.__table__.columns
            if c.name not in exclude_fields
        }
        team_slug = None
        team_name = None
        team_points = None
        if self.team_id:
            team = TeamsStats.query.filter_by(team_id=self.team_id).first()
            if team:
                team_slug = team.slug
                team_name = team.team_name
                team_points = team.points
        data["team_slug"] = team_slug
        data["team_name"] = team_name
        data["team_points"] = team_points
        return data
    
    
class PlayerStatsLastMonth(PlayerStatsBase):
    __tablename__ = 'player_stats_last_month'

class PlayerStats3Months(PlayerStatsBase):
    __tablename__ = 'player_stats_3_months'

class PlayerStats6Months(PlayerStatsBase):
    __tablename__ = 'player_stats_6_months'

class PlayerStats12Months(PlayerStatsBase):
    __tablename__ = 'player_stats_12_months'

class LeaguesInfo(db.Model):
    __tablename__ = 'leagues_info'

    id = db.Column(db.Integer, primary_key=True)
    league_id =  db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), nullable=True)
    prize = db.Column(db.Integer, nullable=True)
    start_date = db.Column(db.String(100), nullable=True)
    tier = db.Column(db.String(10), nullable=True)
    pickem_presence = db.Column(db.Boolean, nullable=True)
    image_url = db.Column(db.String(250), nullable=True)
    teams = db.Column(db.JSON, nullable=True)
    tournament_prizes = db.Column(db.JSON, nullable=True)
    stage_rounds = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.Integer, default=lambda: int(datetime.now(brasilia_tz).timestamp()), nullable=True)
    updated_at = db.Column(db.Integer, default=lambda: int(datetime.now(brasilia_tz).timestamp()), onupdate=lambda: int(datetime.now(brasilia_tz).timestamp()), nullable=True)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class GamesInfo(db.Model):
    __tablename__ = 'games_info'

    id = db.Column(db.Integer, primary_key=True)
    game_id =  db.Column(db.Integer, nullable=False)
    slug = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), nullable=True)
    parsed_status = db.Column(db.String(100), nullable=True)
    bo_type = db.Column(db.Integer, nullable=True)
    winner_team_id = db.Column(db.Integer, nullable=True)
    tier = db.Column(db.String(10), nullable=True)
    start_date = db.Column(db.String(100), nullable=True)
    end_date = db.Column(db.String(100), nullable=True)
    team1_id = db.Column(db.Integer, nullable=False)
    team2_id = db.Column(db.Integer, nullable=False)
    team1_score = db.Column(db.Integer, nullable=True)
    team2_score= db.Column(db.Integer, nullable=True)
    live_coverage = db.Column(db.Boolean, nullable=True)
    league_id = db.Column(db.Integer, nullable=True)
    games = db.Column(db.JSON, nullable=True)
    players_stats = db.Column(db.JSON, nullable=True)
    maps_players_stats = db.Column(db.JSON, nullable=True) 

    created_at = db.Column(db.Integer, default=lambda: int(datetime.now(brasilia_tz).timestamp()), nullable=True)
    updated_at = db.Column(db.Integer, default=lambda: int(datetime.now(brasilia_tz).timestamp()), onupdate=lambda: int(datetime.now(brasilia_tz).timestamp()), nullable=True)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
