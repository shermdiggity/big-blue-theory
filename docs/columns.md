# The columns we actually use

Out of nflverse's 372 play-by-play columns, these are the ones this project uses.
Descriptions are in plain English. Official definitions are in the
[nflverse data dictionary](https://nflreadr.nflverse.com/articles/dictionary_pbp.html).

## Identity and situation
| column | meaning |
|---|---|
| `game_id` | `2026_03_TEN_NYG` = season, week, away team, home team |
| `play_id` | play number within the game. **A float in pbp and an integer in FTN.** Cast before joining. |
| `posteam` / `defteam` | offense / defense on this play (on kickoffs, `posteam` is the *receiving* team) |
| `qtr`, `time`, `game_seconds_remaining` | clock |
| `down`, `ydstogo` | down and distance (`down` is null on kickoffs, XPs and some penalties) |
| `yardline_100` | yards from the opponent's end zone (75 = own 25, 5 = opponent's 5) |
| `score_differential` | offense score minus defense score, before the play |
| `fixed_drive`, `fixed_drive_result` | drive number and how the drive ended (use these, not `drive`) |
| `drive_play_count`, `ydsnet`, `drive_time_of_possession`, `drive_start_yard_line` | official drive summary fields |

## What happened
| column | meaning |
|---|---|
| `desc` | play text. The source of truth when a column looks wrong. |
| `play_type` | `pass`, `run`, `punt`, `field_goal`, `kickoff`, `extra_point`, `qb_kneel`, `qb_spike`, `no_play` (penalty wiped it) |
| `pass`, `rush` | 1 if it was a dropback (includes sacks and scrambles) / a designed run. Also set on `no_play` rows. |
| `yards_gained`, `air_yards`, `touchdown`, `interception`, `fumble_lost`, `sack` | outcome |
| `shotgun`, `no_huddle` | formation flags |
| `passer_player_name`, `receiver_player_name`, `rusher_player_name` (+ `_id`) | who (short names like `M.Nabers`, gsis ids) |

## Value
| column | meaning |
|---|---|
| `ep`, `epa` | expected points before the play, and the change the play caused (offense's view) |
| `wp`, `wpa` | offense win probability before the play, and the change (offense's view). **Flip the sign for the defense.** |
| `success` | 1 if EPA > 0 |
| `xpass`, `pass_oe` | model's probability of a pass in this spot; `pass_oe` = (pass − xpass) × 100 |

## Penalties
| column | meaning |
|---|---|
| `penalty`, `penalty_team`, `penalty_type`, `penalty_yards`, `penalty_player_name` | the (first accepted) flag |

Caveat: the free data measures a penalty from where the play started. It doesn't say what the erased play was worth.
That's what `bbt/penalties.py` works out.

## FTN charting (joined in the `plays` view; credit: *FTN Data via nflverse*)
`is_motion`, `is_play_action`, `is_rpo`, `is_screen_pass`, `n_defense_box`, `n_blitzers`, `n_pass_rushers`,
`read_thrown`, `is_drop`, `is_catchable_ball`, `is_interception_worthy`, `is_throw_away`, `is_qb_out_of_pocket`.
`has_ftn` is false until FTN publishes a game, usually a few days after it's played.
