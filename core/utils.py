# core/utils.py

def get_competition_format(n_teams):
    """
    Format adaptatif pour 12 à 36 équipes.
    - Gère les nombres impairs via un BYE fictif (repos tournant)
    - R16 quand effective >= 16 équipes, QF sinon
    - Aucune équipe n'est exclue du tournoi
    """
    has_bye = (n_teams % 2 != 0)
    effective = n_teams + 1 if has_bye else n_teams  # BYE compté comme équipe fictive

    if n_teams >= 16:
        bracket = 'round_16'
        phases = ['playoff', 'round_16', 'quarter', 'semi', 'final']

        if n_teams >= 24:
            # 24+ équipes : 8 directs + 16 en barrages (8 ties)
            direct = 8
            playoff_participants = 16
            playoff_ties = 8
            eliminated = n_teams - 24
            k = 8 if n_teams >= 32 else 6
        else:
            # 16-23 équipes : formule zéro élimination
            direct = 32 - n_teams
            playoff_participants = n_teams - direct
            playoff_ties = playoff_participants // 2
            eliminated = 0
            k = 4
    else:
        # FORMAT QF (12-15 équipes)
        bracket = 'quarter'
        phases = ['playoff', 'quarter', 'semi', 'final']
        k = 4

        if n_teams >= 8:
            direct = max(0, 16 - n_teams)
            playoff_participants = n_teams - direct
            playoff_ties = playoff_participants // 2
            eliminated = 0
        else:
            direct = n_teams
            playoff_participants = 0
            playoff_ties = 0
            eliminated = 0

    # Nombre total de matchs de ligue
    # Avec BYE : effective est pair, donc effective*k/2 est entier
    total_league_matches = effective * k // 2

    # Matchs "réels" = on retire les matchs contre le BYE fictif
    # (car ces matchs ne sont pas créés)
    real_league_matches = n_teams * k // 2

    # Journées
    if has_bye:
        # Avec impair, chaque journée a (n_teams-1)/2 matchs + 1 repos
        matches_per_matchday = (n_teams - 1) // 2
    else:
        matches_per_matchday = n_teams // 2

    # Label lisible
    if eliminated > 0:
        elim_label = f" — {eliminated} éliminé(s) après ligue"
    else:
        elim_label = " — 0 élimination après ligue ✅"

    fmt_name = 'R16' if bracket == 'round_16' else 'QF'
    bye_label = " (avec repos tournant)" if has_bye else ""
    label = (
        f"Format {fmt_name} — {n_teams} équipes{bye_label} — "
        f"{k} journées — {playoff_ties} barrages{elim_label}"
    )

    return {
        'n_teams': n_teams,
        'effective_teams': n_teams,   # ⚠️ on garde n_teams (BYE est fictif)
        'has_bye': has_bye,
        'opponents_per_team': k,
        'matchdays': k,
        'matches_per_matchday': matches_per_matchday,
        'total_league_matches': real_league_matches,  # ⚠️ matchs réels
        'direct_qualified': direct,
        'playoff_participants': playoff_participants,
        'playoff_ties': playoff_ties,
        'eliminated_after_league': eliminated,
        'bracket': bracket,
        'phases': phases,
        'label': label,
    }