# Art style presets

Style is not “free text only.” Each **preset** bundles:

- Shader and material template expectations in Unity  
- Texture resolution targets and which maps are required  
- ComfyUI graph variant (or LoRA / style references)  
- Art-direction constraints injected into the LLM system prompt  
- Optional post-processing (e.g. edge detection only for toon — often better in-engine)

## Defined presets (v0)

### `realistic_hd_pbr`

- **Intent:** believable PBR, HD readability, physically plausible roughness/metal response.  
- **Textures:** albedo, normal, ORM or M/R/O separate; optional detail normal at 2048–4096 for hero props.  
- **Mesh:** higher triangle budget allowed; emphasize clean silhouettes and good UVs for texture fidelity.  
- **Unity:** Standard Lit or URP Lit; HDRP is optional if the project uses it — document per game template.  
- **Risks:** uncanny or noisy textures; mitigate with denoise nodes and curated negative prompts in the graph.

### `anime_stylized`

- **Intent:** clean anime-inspired look without locking to a single IP; readable forms and controlled highlights.  
- **Textures:** often **simpler** ORM; albedo carries more of the look; normal maps may be subtle.  
- **Mesh:** can be slightly lower poly; silhouette and hair/volume rules matter for characters (characters are a later phase).  
- **Unity:** cel or stepped lighting via custom URP shader or Material variants; outlines may be **in shader** rather than baked to texture.  
- **Risks:** style drift between assets — mitigate with **shared palette** and **reference image lock** per batch.

### `toon_bold`

- **Intent:** bold stepped values, strong rim, playful readability (not necessarily childish).  
- **Textures:** flatter albedo, roughness often pushed to extremes for readability.  
- **Mesh:** exaggerate primary forms slightly; avoid noisy micro-detail that fights the toon shader.  
- **Unity:** dedicated toon shader graph; rim and specular hooks documented in export README.  
- **Risks:** clash with realistic environment props — use **separate material libraries** per preset.

## Mapping presets to the spec

`StudioAssetSpec.style_preset` must be one of the enum values in [json-schema-spec.md](./json-schema-spec.md) (mirrored in `@immersive/studio-types`).

## Extending presets

Adding a new preset requires:

1. Update schema enum + TypeScript types.  
2. Add Unity material template and import checklist.  
3. Add or fork ComfyUI graph; document model weights and licenses.  
4. Add validator rules (e.g. required `material_slots` for that preset).

## Consistency tactics (all presets)

- **Batch locking:** same `seed` strategy and reference images for a set of props in one environment.  
- **Palette:** optional `palette[]` in the spec; validator enforces hex format.  
- **Negative prompts:** preset-specific defaults, not user-supplied only.  
- **Tri count caps:** per preset defaults with override in spec for hero assets.
