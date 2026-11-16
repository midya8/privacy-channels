"""Exact randomized binary tests for one listed directed secret pair.

Neyman-Pearson fractional-knapsack ordering, explicit primal/dual witnesses.
No sampled test, classifier training or deployed-mechanism certification.
"""
from fractions import Fraction as F
from .core import encode, rational, validate_channel


def testing_tradeoff(channel, null_index, alternative_index, alpha):
    c = validate_channel(channel)
    if len(c['secrets']) > 4 or len(c['outputs']) > 8:
        raise ValueError('testing is limited to 4 secrets and 8 outputs')
    if (type(null_index) is not int or type(alternative_index) is not int or
            null_index == alternative_index or
            sorted([null_index, alternative_index]) not in c['neighbors']):
        raise ValueError('testing needs one listed directed pair of distinct integer secret indices')
    budget = rational(alpha, 'type-I budget')
    p, q = c['probabilities'][null_index], c['probabilities'][alternative_index]
    free = [i for i, (a, b) in enumerate(zip(p, q)) if not a and b]
    absent = [i for i, (a, b) in enumerate(zip(p, q)) if not a and not b]
    ratios = sorted({b/a for a, b in zip(p, q) if a}, reverse=True)
    groups = [[i for i, (a, b) in enumerate(zip(p, q)) if a and b/a == ratio]
              for ratio in ratios]
    used = F(0)
    power = sum((q[i] for i in free), F(0))
    vertices = [{'alpha': '0', 'beta': str(1-power), 'power': str(power)}]
    pieces = []
    phi = [F(int(i in free)) for i in range(len(p))]
    threshold = F(0)
    for ratio, group in zip(ratios, groups):
        mass_p = sum((p[i] for i in group), F(0))
        mass_q = sum((q[i] for i in group), F(0))
        pieces.append({'alpha_lower': str(used), 'alpha_upper': str(used+mass_p),
                       'beta_intercept': str(1-power+ratio*used),
                       'slope_magnitude': str(ratio), 'tie_outputs': group,
                       'null_mass': str(mass_p), 'alternative_mass': str(mass_q)})
        fraction = max(F(0), min(F(1), (budget-used)/mass_p))
        for i in group:
            phi[i] = fraction
        if used <= budget < used+mass_p:
            threshold = ratio
        used += mass_p
        power += mass_q
        vertices.append({'alpha': str(used), 'beta': str(1-power), 'power': str(power)})
    actual_alpha = sum((a*f for a, f in zip(p, phi)), F(0))
    actual_power = sum((b*f for b, f in zip(q, phi)), F(0))
    terms = []
    for i, (a, b, f) in enumerate(zip(p, q, phi)):
        coefficient = b-threshold*a
        positive = max(coefficient, F(0))
        slack = positive-coefficient*f
        assert slack == 0
        terms.append({'output_index': i, 'null_probability': str(a),
                      'alternative_probability': str(b), 'reject_probability': str(f),
                      'dual_coefficient': str(coefficient), 'dual_positive_part': str(positive),
                      'complementarity_slack': str(slack)})
    dual = threshold*budget + sum((F(term['dual_positive_part']) for term in terms), F(0))
    assert used == 1 and power == 1 and actual_alpha == budget and dual == actual_power
    return {'schema_version': 1, 'channel': encode(c), 'null_index': null_index,
            'alternative_index': alternative_index, 'alpha_budget': str(budget),
            'test': [str(v) for v in phi], 'actual_alpha': str(actual_alpha),
            'power': str(actual_power), 'beta': str(1-actual_power),
            'free_power_outputs': free, 'both_zero_outputs': absent,
            'segments': pieces, 'vertices': vertices,
            'dual': {'threshold': str(threshold), 'upper_power': str(dual),
                     'budget_slack': str(threshold*(budget-actual_alpha)),
                     'gap': str(dual-actual_power), 'terms': terms},
            'scope': 'exact optimal randomized binary test for one supplied listed directed secret pair; false-positive budget under null, false-negative probability under alternative; not a trained classifier, actual attack or deployed privacy guarantee'}
