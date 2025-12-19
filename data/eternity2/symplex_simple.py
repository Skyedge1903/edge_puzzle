import time
import numpy as np
import pandas as pd
from pulp import (
    LpProblem, LpVariable, LpMaximize,
    lpSum, LpContinuous, PULP_CBC_CMD
)

# ==============================
# PARAMÈTRES
# ==============================
SIZE = 16
ROT = 4
TILES_CSV = "eternity2_256.csv"
OUT_CSV = "best_eternity2_solution.csv"

# Directions
N, E, S, W = 0, 1, 2, 3

# ==============================
# CHARGEMENT DES TUILES
# ==============================
print("Chargement des tuiles...")
tiles = pd.read_csv(TILES_CSV, header=None).values.astype(int)
NTILES = len(tiles)

# Pré-calcul rotations
print("Pré-calcul des rotations...")
t_rot = np.zeros((NTILES * ROT, 4), dtype=int)
for p in range(NTILES):
    for r in range(ROT):
        t_rot[p * ROT + r] = np.roll(tiles[p], -r)

# Couleurs distinctes
COLORS = sorted(set(t_rot.flatten()))
NC = len(COLORS)
color_index = {c: i for i, c in enumerate(COLORS)}

print(f"{NTILES} tuiles, {NC} couleurs distinctes")

# ==============================
# INDEXATION DES ARÊTES INTERNES
# ==============================
edges = []
edge_index = {}

eid = 0
for i in range(SIZE):
    for j in range(SIZE):
        if j + 1 < SIZE:
            edge_index[(i, j, E)] = eid
            edges.append((i, j, E))
            eid += 1
        if i + 1 < SIZE:
            edge_index[(i, j, S)] = eid
            edges.append((i, j, S))
            eid += 1

NE = len(edges)
print(f"{NE} arêtes internes (score max théorique = {NE})")

# ==============================
# MODÈLE LP
# ==============================
print("Construction du modèle LP...")
t_start = time.time()

prob = LpProblem("Eternity2_LP_Edges", LpMaximize)

# ==============================
# VARIABLES
# ==============================

# Pose des pièces (RELAXATION LP)
x = {}
for i in range(SIZE):
    for j in range(SIZE):
        for p in range(NTILES):
            for r in range(ROT):
                x[(i, j, p, r)] = LpVariable(
                    f"x_{i}_{j}_{p}_{r}", 0, 1, LpContinuous
                )

# Couleur portée par chaque arête
z = {}
for e in range(NE):
    for c in range(NC):
        z[(e, c)] = LpVariable(
            f"z_{e}_{c}", 0, 1, LpContinuous
        )

# Score d’arête
y = {}
for e in range(NE):
    y[e] = LpVariable(f"y_{e}", 0, 1, LpContinuous)

print("Variables créées.")

# ==============================
# CONTRAINTES
# ==============================
print("Création des contraintes...")
t_c = time.time()

# 1️⃣ Une pièce par case
for i in range(SIZE):
    for j in range(SIZE):
        prob += lpSum(x[(i, j, p, r)] for p in range(NTILES) for r in range(ROT)) == 1

# 2️⃣ Chaque pièce utilisée exactement une fois
for p in range(NTILES):
    prob += lpSum(
        x[(i, j, p, r)]
        for i in range(SIZE)
        for j in range(SIZE)
        for r in range(ROT)
    ) == 1

# 3️⃣ Une seule couleur par arête
for e in range(NE):
    prob += lpSum(z[(e, c)] for c in range(NC)) == 1

# 4️⃣ Lien pièce → couleur d’arête (LOCAL, OPTIMISÉ)
for (i, j, d), e in edge_index.items():

    if d == E:
        # Tuile gauche (E)
        for p in range(NTILES):
            for r in range(ROT):
                c = color_index[t_rot[p * ROT + r][E]]
                prob += z[(e, c)] >= x[(i, j, p, r)]

        # Tuile droite (W)
        for p in range(NTILES):
            for r in range(ROT):
                c = color_index[t_rot[p * ROT + r][W]]
                prob += z[(e, c)] >= x[(i, j + 1, p, r)]

    elif d == S:
        # Tuile haut (S)
        for p in range(NTILES):
            for r in range(ROT):
                c = color_index[t_rot[p * ROT + r][S]]
                prob += z[(e, c)] >= x[(i, j, p, r)]

        # Tuile bas (N)
        for p in range(NTILES):
            for r in range(ROT):
                c = color_index[t_rot[p * ROT + r][N]]
                prob += z[(e, c)] >= x[(i + 1, j, p, r)]

# 5️⃣ Définition du score
for e in range(NE):
    for c in range(NC):
        prob += y[e] <= z[(e, c)]

print(f"Contraintes créées en {time.time() - t_c:.2f}s")

# ==============================
# OBJECTIF
# ==============================
prob += lpSum(y[e] for e in range(NE))

print("Modèle prêt.")
print("Variables :", len(prob.variables()))
print("Contraintes :", len(prob.constraints))

# ==============================
# RÉSOLUTION
# ==============================
print("Lancement du simplexe (LP relaxation)...")
solver = PULP_CBC_CMD(
    msg=1,
    threads=4,
    timeLimit=1800
)

t_solve = time.time()
prob.solve(solver)
elapsed = time.time() - t_solve

print(f"Résolution terminée en {elapsed/60:.2f} minutes")
print("Statut solveur :", prob.status)

# Score LP
lp_score = sum(y[e].varValue for e in range(NE))
print(f"Score LP obtenu : {lp_score:.2f} / {NE}")

# ==============================
# EXPORT CSV (COMPATIBLE)
# ==============================
print("Export de la solution CSV...")
with open(OUT_CSV, "w") as f:
    for i in range(SIZE):
        for j in range(SIZE):
            best_val = -1
            best_pr = None
            for p in range(NTILES):
                for r in range(ROT):
                    v = x[(i, j, p, r)].varValue
                    if v is not None and v > best_val:
                        best_val = v
                        best_pr = (p, r)
            p, r = best_pr
            f.write(f"{i},{j},{p+1},{r}\n")

print("Fichier généré :", OUT_CSV)
print("Terminé.")
