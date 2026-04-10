# Vision and scope

## Vision

Build an internal **Video Game Generation Studio**: the user describes what they want in natural language, and the system produces **importable 3D assets** for a **Unity-style workflow** (primary target: Unity), with support for **multiple visual styles** on the same technical pipeline.

## Target visual styles (realistic scope)

We want **one pipeline** that can be steered toward distinct looks:

1. **Realistic HD (PBR)**  
   Physically based materials, high-resolution textures where appropriate, believable proportions and lighting response. Expect heavier texture work and more demanding mesh cleanup.

2. **Anime stylized**  
   Clean reads, controlled specular, often flatter or gradient-driven shading, color harmony, optional outline treatment in-engine (not only in textures).

3. **Toon / bold**  
   Strong value steps, clear rim lighting conventions, simplified materials, readable silhouettes at medium distance.

**Important:** “Completely realistic HD” and “anime/toon” differ mainly in **shader templates, texture treatment, and art direction constraints**, not in the core idea of “mesh + UVs + textures + manifest.” The studio should encode style as **presets** (see [art-style-presets.md](./art-style-presets.md)), not as one-off prompts only.

## In scope

- Text → **validated structured spec** (JSON) for each asset or batch.
- Generation of **meshes and textures** suitable for Unity import (GLTF/FBX + PBR maps).
- **Style presets** that map to material templates, texture resolution targets, and post-processing expectations.
- **Reproducibility metadata** in job manifests (seeds, model IDs, graph versions).
- **Local-first** execution on a capable GPU, with optional paid APIs later.

## Out of scope (initial phases)

- A full playable game or level generator (we may output **props** and **environment pieces** first).
- Guaranteed “one click, no human review” AAA quality for all styles.
- Hosting a public multi-tenant SaaS (unless explicitly chosen later; security and cost model differ).

## Success criteria (v1)

- Import a generated pack into Unity with **predictable scale** (1 unit = 1 meter), **named materials**, and a **working collider** for simple props.
- Switching **style preset** changes the look materially while keeping the same mesh topology or clearly defined variant rules.
- A developer can reproduce a build from the **manifest** and pinned toolchain versions.

## Principles

- **Spec first:** natural language is compiled into a strict schema before expensive generation.
- **Preset-driven consistency:** prompts alone are insufficient for a multi-style studio.
- **Validate at boundaries:** after LLM, after image gen, after mesh export, after Unity import.
