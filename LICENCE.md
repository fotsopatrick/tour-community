# Licence — Tour de contrôle, édition Community

**Version 1.0 — 9 août 2026**
Éditeur : Patrick Orel Kamdem Fotso — Code Nomi Nomi
Contact : contact@matourdecontrole.fr

---

## En une phrase

Les modules de cette édition sont **libres de lire, d'installer et de
modifier** pour votre propre usage, sous les termes de l'AGPL-3.0. Le **cœur
de la tour n'est pas ici** : les agents, le coffre, les circuits et la
gouvernance restent une édition séparée, sous licence propriétaire.

---

## 1. Ce que vous avez le droit de faire

1. **Lire le code** de n'importe lequel des 16 modules de cette édition.
2. **L'installer et l'utiliser**, sur autant de serveurs que vous voulez.
3. **Le modifier**, et garder vos modifications pour vous (AGPL : si vous
   servez une version modifiée à des tiers sur un réseau, vous devez leur
   donner accès au code modifié — c'est l'esprit « libre à lire »).
4. **Vous en inspirer** pour votre propre travail.

## 2. Ce qui est HORS de cette édition

1. Le **cœur de la tour** : l'équipage d'agents (`tour_equipage`),
   l'atelier (`tour_atelier`), le coffre des secrets (`tour_vault`), le
   moteur de circuits (`tour_circuits`), les garde-fous avancés, la
   gouvernance et la détection de compétences. Ces modules ne sont PAS
   publiés ici.
2. Leurs **données, secrets et clés** : rien de ce qui permet de faire
   tourner le cœur n'est dans ce dépôt.
3. Les fichiers **chiffrés** (`*.enc`) : leur contenu ne se débloque
   qu'avec le mot de passe administrateur de l'édition complète. Un
   déchiffrement sans ce mot de passe est inutile : la clé est dérivée
   par dérivation lente (PBKDF2, 600 000 itérations) et l'algorithme est
   AES-256 — casser la clé exige des milliers de serveurs.

## 3. Ce que vous n'avez pas le droit de faire

1. **Revendre cette édition** en l'état, ou en faire un service revendu à
   des tiers, sans un accord écrit séparé.
2. **Présenter le cœur de la tour comme libre** : il ne l'est pas.
3. **Retirer les mentions d'origine** dans le code et l'interface.

## 4. Pourquoi cette distinction

La tour complète vit à https://matourdecontrole.fr. L'édition Community est
la vitrine : ce qu'on peut lire et installer sans dévoiler la recette. Le
cœur — ce qui rend la tour unique — reste protégé, et c'est voulu.
