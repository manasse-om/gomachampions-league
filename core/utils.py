# core/utils.py

def get_competition_format(n_teams):
    """
    Format adaptatif pour 12 à 36 équipes.
    - Minimise les éliminations après la ligue
    - Gère les nombres impairs (bye)
    - R16 quand >= 16 équipes, QF sinon
    """
    has_bye = n_teams % 2 != 0
    effective = n_teams - 1 if has_bye else n_teams

    if effective >= 16:
        bracket = 'round_16'
        phases = ['playoff', 'round_16', 'quarter', 'semi', 'final']

        if effective >= 24:
            # 24+ équipes : 8 directs fixes + 16 en barrages (8 ties)
            direct = 8
            playoff_participants = 16
            playoff_ties = 8
            eliminated = effective - 24
            k = 8 if effective >= 32 else 6

        else:
            # 16-23 équipes : formule zéro élimination
            # direct = 32 - effective
            # playoff = 2 * effective - 32
            direct = 32 - effective
            playoff_participants = effective - direct
            playoff_ties = playoff_participants // 2
            eliminated = 0
            k = 4

    else:
        # FORMAT QF (12-15 équipes)
        bracket = 'quarter'
        phases = ['playoff', 'quarter', 'semi', 'final']
        k = 4

        if effective >= 8:
            # Formule zéro élimination pour QF
            # direct = 16 - effective
            direct = max(0, 16 - effective)
            playoff_participants = effective - direct
            playoff_ties = playoff_participants // 2
            eliminated = 0
        else:
            direct = effective
            playoff_participants = 0
            playoff_ties = 0
            eliminated = 0

    total_league_matches = effective * k // 2
    matches_per_matchday = effective // 2

    # Label lisible
    if eliminated > 0:
        elim_label = f" — {eliminated} éliminé(s) après ligue"
    else:
        elim_label = " — 0 élimination après ligue ✅"

    fmt_name = 'R16' if bracket == 'round_16' else 'QF'
    label = (
        f"Format {fmt_name} — {n_teams} équipes — "
        f"{k} journées — {playoff_ties} barrages{elim_label}"
    )

    return {
        'n_teams': n_teams,
        'effective_teams': effective,
        'has_bye': has_bye,
        'opponents_per_team': k,
        'matchdays': k,
        'matches_per_matchday': matches_per_matchday,
        'total_league_matches': total_league_matches,
        'direct_qualified': direct,
        'playoff_participants': playoff_participants,
        'playoff_ties': playoff_ties,
        'eliminated_after_league': eliminated,
        'bracket': bracket,
        'phases': phases,
        'label': label,
    }