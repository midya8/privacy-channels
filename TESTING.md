# Exact randomized testing tradeoffs

`testing_tradeoff(channel, null_index, alternative_index, alpha)` computes the best binary test for one **listed directed pair** of supplied secret laws. It returns the whole type-I/type-II curve, plus an attaining randomized test and exact dual certificate at the requested false-positive budget.

This uses established Neyman-Pearson testing, not a new privacy theorem or a trained classifier. The input is a finite probability table, not a dataset or a deployed program. A pair-specific curve is not a whole-channel guarantee and does not cover unlisted secret pairs.

## Convention and optimization

Let `P` be the null secret's output law and `Q` the alternative secret's law. A test supplies a rejection probability `phi_y` in `[0,1]` for each observed output. Thus

```text
actual alpha = sum_y P_y phi_y       false-positive probability
power        = sum_y Q_y phi_y       rejection under the alternative
beta         = 1 - power            false-negative probability.
```

For each budget `a` in `[0,1]`, maximize power subject to `P.phi <= a`. Randomization is allowed. The returned canonical test uses the full budget, even if power has already reached one and additional rejection can only spend budget without increasing power.

Outputs with `P=0,Q>0` give free power and are always rejected. Outputs with `P=Q=0` have no effect and receive rejection probability zero. Other outputs are grouped by exact equal `Q/P`, ordered from largest ratio to smallest. Entire earlier groups are rejected, later groups are not, and the boundary group uses one common rational rejection fraction. A group with `Q=0,P>0` has ratio zero and may fill unused budget on a zero-beta tail.

Each positive-null-mass group adds one affine segment. The report retains the full segment boundaries, beta intercept and slope magnitude, group output indices, both group masses and every curve vertex. The alpha-zero vertex may have beta below one because singular alternative mass can be recognized without false positives. Segments cover all of `[0,1]`, including any flat tail. Different canonical tests can have the same optimum when ratios tie; this is not a uniqueness claim.

## Exact primal/dual witness

For any threshold `lambda >= 0` and any feasible test,

```text
Q.phi = lambda P.phi + sum_y (Q_y-lambda P_y) phi_y
      <= lambda a + sum_y max(Q_y-lambda P_y,0).
```

The algorithm selects a boundary likelihood ratio as `lambda` (zero at budget one). The requested test attains that upper bound. Every output has its signed dual coefficient, nonnegative positive part and complementary slack

```text
max(Q_y-lambda P_y,0) - (Q_y-lambda P_y) phi_y = 0.
```

The report also returns `lambda*(a-P.phi)=0` and the exact primal/dual gap zero. These equalities show optimality at the requested budget without trusting a rounded plot or a few sampled tests. All arithmetic is rational. No generic LP solver is used in production.

For a full affine segment, the group order yields a fixed threshold and affine attaining tests throughout that segment. This gives the entire curve, not interpolation between unrelated point queries.

## Why randomization matters

Use the original randomized-response laws

```text
P = [3/4, 1/4]
Q = [1/4, 3/4].
```

At alpha budget `1/8`, no nonempty deterministic rejection event fits the budget. Its best power is zero, beta one. The randomized test `[0,1/2]` has alpha `1/8`, power `3/8` and beta `5/8`. Its dual threshold is three and the dual power bound is `3*(1/8)=3/8`.

The complete curve has beta `1-3a` on `0 <= a <= 1/4`, then `(1-a)/3` on `1/4 <= a <= 1`. The break is a change in the likelihood-ratio group, not a change in a trained decision rule. This is an exact developed finite control, not an observed attack success rate.

## Relation to hockey-stick privacy queries

For every multiplicative factor `t >= 1`,

```text
max_a [optimal_power(a) - t*a]
    = sum_y max(Q_y-t P_y,0).
```

The right side is the existing point audit's **reverse directed pair**, alternative-to-null. Maximizing the affine objective over all curve vertices suffices. Reversing `P,Q` changes the testing problem; beta, power and delta are different quantities. The existing privacy point audit still maximizes over all listed directions. Its numeric domain and the adaptive clipped-mass bounds are unchanged.

Secret-independent stochastic postprocessing cannot increase optimal testing power at a fixed alpha budget: any test of the postprocessed output pulls back through the kernel to a randomized test of the original output with the same alpha and power. Tests check that construction explicitly on 20 seeded channel/kernel pairs and five budgets each. This does not certify that an external program uses the supplied kernel or fresh randomness.

## Run and strict contract

```python
from privacylab import testing_tradeoff

report = testing_tradeoff(channel, null_index=0, alternative_index=1, alpha='1/8')
assert report['dual']['gap'] == '0'
```

```sh
python -m privacylab testing examples/testing-input.json
python examples/verify_wheel.py
```

The request has exactly `schema_version`, `channel`, `null_index`, `alternative_index` and `alpha`. Version is integer one. Indices must be distinct actual integers, not bools, and their undirected edge must be listed in the channel. No omission is silently treated as permission to audit another pair.

The testing domain is at most four secrets and eight outputs; the original static/adaptive domains remain unchanged. All existing exact probability, row-normalization, label and neighbor checks apply. Alpha is an exact rational in `[0,1]`, with the existing 512-bit input-component and 160-character string limits. Floats, bools, nonfinite values, duplicate/unknown fields and oversized input fail. A JSON parser-recursion failure is a controlled input error. Computed ratios and curve coefficients can exceed the original point audit's factor cap: they are exact internally and are not fed through the capped point-factor parser. They are not silently clipped.

## Verification and limits

Twelve added tests cover:

- An independent LP-vertex oracle, enumerating all box vertices and all intersections of one fractional coordinate with the alpha constraint. It does not sort likelihood ratios. Twenty-four seeded three-secret/four-output channels check both directions of each listed edge, every affine segment at endpoints and three interior points, plus each requested test and all dual terms.
- All 100 ordered pairs of three-output laws with denominator three, at four budgets each, checked against the independent vertex oracle.
- Explicit randomization gaps, ratio ties, identical laws, disjoint support, free singular mass, absent outputs, zero/one budgets, all curve groups and vertices, output permutations, reversed pairs, omitted adjacency, maximum domain, tiny mass `10^-100` and a large exact likelihood ratio.
- Exact hockey-stick duality at five factors, stochastic postprocessing with explicit pulled-back tests, strict CLI errors, no input mutation and unchanged global RNG state.

The full suite has 75 tests. The installed-wheel verifier runs them all outside checkout, checks all eight module origins before and after, compares seven complete module CLI reports and regenerates all three original figures. The six earlier complete reports and all three SVG files are unchanged.

The Neyman-Pearson lemma, randomized tie rule and optimality argument are standard. See [Stanford STATS 300A, lecture 13, section 13.1](https://web.stanford.edu/~lmackey/stats300a/doc/stats300a-fall15-lecture13.pdf). The finite dual inequality above is included so the convention and certificate can be checked directly. The existing [privacy derivation](DESIGN.md) and [factor frontier](FRONTIER.md) provide the hockey-stick context.

This does not train or evaluate a classifier, estimate distributions, discover private secrets, verify secure randomness, audit deployed software, compute statistical confidence intervals, optimize unknown-mechanism composition or implement a production privacy accountant. The returned test is optimal only for the supplied two laws and stated randomization convention.
