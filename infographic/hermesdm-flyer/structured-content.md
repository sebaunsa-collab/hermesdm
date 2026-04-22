# HermesDM — Flyer Informativo

## Overview
HermesDM es un motor de juego de Dungeons & Dragons 5e integrado en Telegram. Permite tirar dados, resolver combate, gestionar personajes y generar narrativa inmersiva con imágenes, todo desde un grupo de Telegram.

## Learning Objectives
The viewer will understand:
1. Qué es HermesDM y por qué es interesante
2. Sus características principales
3. Cómo empezar a jugar
4. La arquitectura técnica

---

## Section 1: ¿Qué es HermesDM?

**Key Concept**: Un motor de D&D 5e dentro de Telegram que automatiza dados, combate y narrativa.

**Content**:
- Motor de juego de Dungeons & Dragons 5ta edición
- Integración directa con Telegram (no necesita app externa)
- Soporta tiradas de dados, combate táctico y narrativa con imágenes
- 274 tests automatizados verificando correctitud

**Visual Element**:
- Type: icon illustration
- Subject: dado d20 con logo de Telegram
- Treatment: hand-drawn style, prominent center placement

**Text Labels**:
- Headline: "¿Qué es HermesDM?"
- Subhead: "Tu mesa de D&D dentro de Telegram"
- Tagline: "D&D 5e · Dados · Combate · Narrativa"

---

## Section 2: Características Principales

**Key Concept**: Módulos de juego que cubren todo lo necesario para una campaña.

**Content**:
- **Motor de Dados**: Tiradas XdY+Z con crítico y pifia automática
- **Combate Táctico**: Ataques con ventaja/desventaja, hechizos, daño
- **Gestión de Personajes**: Hojas de personaje, stats, habilidades
- **Narrativa Inteligente**: Generador de escenas + imágenes con IA
- **Gestor de Turnos**: Iniciativa, orden de combate, estados

**Visual Element**:
- Type: icon grid (5 icons)
- Subject: dado, espada/escudo, pergamino, imagen, reloj
- Treatment: hand-drawn icons in a 2x3 grid

**Text Labels**:
- Headline: "Características"
- Labels: "Dados", "Combate", "Personajes", "Narrativa", "Turnos"

---

## Section 3: Comandos Básicos

**Key Concept**: Comandos simples para empezar a jugar.

**Content**:
- `/roll 1d20` — Tira un dado de 20 caras
- `/j ataco al orco` — Ejecuta una acción con dado
- `/newgame` — Inicia una nueva campaña
- `/me se esconde` — Narración sin dado
- `/help` — Muestra todos los comandos

**Visual Element**:
- Type: command list with icons
- Subject: terminal/chat bubbles with commands
- Treatment: monospace font for commands, clean list

**Text Labels**:
- Headline: "Empezá a Jugar"
- Subhead: "Comandos básicos"
- Command labels: "/roll", "/j", "/newgame", "/me", "/help"

---

## Section 4: Sistema de Dados

**Key Concept**: Tiradas precisas con notación estándar de D&D.

**Content**:
- Notación: XdY+Z (ej: 2d6+3)
- Crítico (Nat 20): Éxito automático + daño doble
- Pifia (Nat 1): Fallo automático + complicación
- Modificador de ventaja/desventaja

**Visual Element**:
- Type: dice illustration
- Subject: d20 highlight with roll result
- Treatment: large number emphasis, crit/fumble callouts

**Text Labels**:
- Headline: "Motor de Dados"
- Notation example: "2d6+3"
- Crit label: "¡Crítico!"
- Fumble label: "¡Pifia!"

---

## Section 5: Combate Táctico

**Key Concept**: Sistema completo de combate D&D 5e.

**Content**:
- Ataques cuerpo a cuerpo con bonus de rabia
- Hechizos con CD (Difficulty Class)
- Ventaja y desventaja automáticas
- Aplicación de daño a HP

**Visual Element**:
- Type: combat icon
- Subject: crossed swords with shield
- Treatment: dynamic, action-oriented

**Text Labels**:
- Headline: "Combate"
- Labels: "Ataque", "Hechizo", "Ventaja", "Daño"

---

## Section 6: Imágenes con IA

**Key Concept**: Genera escenas de campaña con inteligencia artificial.

**Content**:
- Pollinations.ai: Rápido y gratuito para escenas rápidas
- MiniMax: Alta calidad para momentos épicos
- Genera prompts narrativos automáticamente

**Visual Element**:
- Type: image frame mockup
- Subject: fantasy scene (cavern, dragon, dungeon)
- Treatment: illustration style matching campaign mood

**Text Labels**:
- Headline: "Imágenes IA"
- Subhead: "Escenas generadas automáticamente"
- Labels: "Rápido", "Épico", "Automático"

---

## Section 7: Arquitectura Técnica

**Key Concept**: Dos bots separados para evitar conflictos.

**Content**:
- Token A (@Hermeciano_bot): Chat 1:1 con Sherman
- Token B (@HermesDM_bot): Grupo D&D
- 274 tests unitarios pasando
- 3 fases de desarrollo completadas

**Visual Element**:
- Type: architecture diagram
- Subject: two separate bot icons with arrows
- Treatment: simple flow diagram, technical but clean

**Text Labels**:
- Headline: "Arquitectura"
- Label A: "@Hermeciano_bot → 1:1"
- Label B: "@HermesDM_bot → Grupo D&D"

---

## Data Points (Verbatim)

### Statistics
- "274 tests passing"
- "XdY+Z" (notación de dados)

### Key Terms
- **HermesDM**: Motor de D&D 5e para Telegram
- **Crítico (Nat 20)**: 20 natural en d20 = éxito automático
- **Pifia (Nat 1)**: 1 natural en d20 = fallo automático
- **Ventaja/Desventaja**: Tira 2d20, usa el mayor/menor

### Commands
- `/roll 1d20` — Tirar dados
- `/j` — Acción de personaje
- `/newgame` — Nueva campaña
- `/me` — Narración libre
- `/help` — Ayuda

---

## Design Instructions

### Style Preferences
- Hand-drawn, craft/paper aesthetic
- Warm, friendly colors (craft-handmade default)
- Minimalist: clean canvas, ample whitespace
- No complex background textures

### Layout Preferences
- Bento-grid: multiple feature sections
- Landscape 16:9 aspect ratio
- Visual hierarchy: title → features → commands → architecture

### Other Requirements
- Spanish language throughout
- Shareable as a product flyer
- Promote as open source / community project
