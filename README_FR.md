🇬🇧 English version (default)  
🇫🇷 [Lire la version française](README_FR.md)

# 🎭 Orion4D Anaglyph for ComfyUI

**Orion4D Anaglyph** est un custom node performant conçu pour transformer des images 2D en rendus stéréoscopiques (3D) via une carte de profondeur (*depth map*). Il offre un contrôle total sur la parallaxe, la convergence et le traitement de la profondeur pour un confort visuel optimal.

---

## 🚀 Fonctionnalités Clés

* **Compatibilité Totale** : Fonctionne avec Depth Anything (V2/V3), Marigold, ZoeDepth, MiDaS, ou des cartes éditées à la main.
* **Modes de Rendu Variés** : Supporte le Rouge/Cyan (Dubois, Couleur, Gris) et le Rouge/Bleu.
* **Sorties Multiples** : Génère l'anaglyphe, le Side-by-Side (SBS), les vues gauche/droite isolées et la depth map traitée.
* **Gestionnaire de Presets** : Interface JS intégrée pour sauvegarder, charger et mettre à jour vos réglages favoris.
* **Traitement Natif** : Implémentation PyTorch optimisée pour la rapidité et la compatibilité.

---

## 🛠 Installation

Copiez le dossier `Orion4D_anaglyph` dans votre répertoire de nodes personnalisés :

```text
ComfyUI/custom_nodes/Orion4D_anaglyph
```

### Structure du dossier
```text
Orion4D_anaglyph/
├── orion4d_anaglyph.py    # Logique principale
├── preset_manager.py      # Gestion des JSON
├── web/                   # Interface utilisateur (JS)
└── presets/               # Vos configurations sauvegardées
```

---

## ⚙️ Paramètres de Configuration

| Paramètre | Description | Valeur Recommandée |
| :--- | :--- | :--- |
| **strength** | Intensité de l'effet 3D (parallaxe). | `16` à `32` |
| **convergence** | Point focal où l'image semble être sur l'écran. | `0.5` |
| **shift_mode** | Méthode de décalage (`symmetric`, `left_static`, `right_static`). | `symmetric` |
| **depth_blur** | Adoucit les bords pour réduire les artefacts. | `5` à `9` |
| **depth_invert** | Inverse la profondeur si le relief paraît erroné. | Selon la source |

---

## 🔄 Flux de Travail (Workflow)

Le node s'insère idéalement après un estimateur de profondeur :

```text
[ Image Source ] 
      │
      ├─► [ Depth Anything V3 ] ──► (Depth Map) ──┐
      └───────────────────────────► (Image RGB)  ──┴─► [ Orion4D Anaglyph ]
                                                              │
                                        ┌─────────────────────┴─────────────────────┐
                                  [ Anaglyph ]        [ Side-by-Side ]        [ Left/Right ]
```

---

## 🎨 Modes d'Anaglyphes Disponibles

* **Optimized Dubois (Rouge/Cyan)** : Le standard pour la fidélité des couleurs et la réduction du *ghosting*.
* **Color / Half-Color** : Préserve davantage l'éclat original au prix de potentiels reflets résiduels.
* **Gray** : Idéal pour une clarté maximale du relief sans distraction chromatique.

---

## 🆘 Dépannage & Conseils

### 👁️ Fatigue visuelle ?
* Réduisez la valeur de `strength`.
* Ajustez la `convergence` pour placer le sujet principal sur le plan de l'écran.
* Augmentez le `depth_blur`.

### 🔀 Effet inversé ?
1.  Cochez `depth_invert`.
2.  Si cela ne suffit pas, utilisez l'option `swap_eyes`.

### 🖼️ Étirements sur les bords (Warping)
Il s'agit d'une limitation de la reprojection 2D vers 3D. Pour minimiser cela :
* Utilisez `padding_mode: border`.
* Réduisez le `depth_contrast`.
* Utilisez une carte de profondeur plus précise (ex: Depth Anything V3 Large).

---


### 🌟 **Soutenez le projet**
Si cet outil vous est utile, n'hésitez pas à laisser une ⭐ sur GitHub !

**Développé avec ❤️ pour la communauté ComfyUI par Orion4D**

<a href="https://ko-fi.com/orion4d">
<img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Buy Me A Coffee" height="41" width="174">
</a>

</div>
