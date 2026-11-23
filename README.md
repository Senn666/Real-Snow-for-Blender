# Real Snow for Blender 5.3

An updated build of the classic **Real Snow** add-on that works on **Blender 5.3** (and 4.2+).

The original add-on by Marco Pavanello was discontinued in 2024 and its official extension only supports Blender 4.2. This repository keeps it usable on current Blender releases by fixing the API changes that would otherwise break it.

## Compatibility

| Blender | Supported |
| --- | --- |
| 5.3 | ✅ Tested (5.3.0) |
| 5.0 – 5.2 | Expected to work |
| 4.2 – 4.5 | Expected to work |

## Installation

1. Download `real_snow_5.3.zip` from the [latest release](https://github.com/Senn666/Real-Snow-for-Blender/releases/latest).
2. In Blender, go to **Edit → Preferences → Add-ons → Install from Disk…**
3. Select the downloaded zip and confirm.
4. Search for **Real Snow** and enable the checkbox.

## Usage

1. Select a mesh object.
2. Open the **N** sidebar in the 3D Viewport.
3. Go to the **Real Snow** tab.
4. Adjust the snow parameters and click the generate button.

The generated snow mesh is parented to the source object, uses a `Snow` material, and is placed in a `Snow` collection.

## What changed from upstream

- **Principled BSDF sockets**: Blender 4.1+ renamed and reordered the shader inputs. The original code used numeric indices (`inputs[8]`, `inputs[18]`, …), which now point to the wrong sockets and raise `TypeError`. All access is now by socket name / identifier.
- **Cycles adaptive subdivision**: `Object.cycles.use_adaptive_subdivision` was removed in Blender 4.2+. Now guarded with a capability check.
- **Material displacement**: `Material.cycles.displacement_method` moved to `Material.displacement_method`. Now uses the new property when available.
- **Memory leak fix**: the upstream `area()` function called `bm_obj.free` without parentheses; fixed.
- Added compatibility checks so the add-on degrades gracefully instead of throwing exceptions.

## Credits & license

- Original add-on: [Marco Pavanello / real-snow](https://gitlab.com/marcopavanello/real-snow), co-author Drew Perttula.
- Distributed under the upstream project's license (see [LICENSE](LICENSE)).
- This repository only contains the compatibility patch and packaging; all credit for the original work goes to the upstream authors.
