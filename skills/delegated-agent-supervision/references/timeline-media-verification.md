# Timeline and Media Artifact Verification

Use this after delegating video, animation, audio-sequence, slideshow, or other
timeline-driven work. It catches structural errors that compile and typecheck
cannot see.

## Failure pattern

A delegated Remotion edit typechecked cleanly, but both compositions used one
hardcoded duration. After transition overlaps, the real timelines ended at 744
and 835 frames while the composition was fixed at 765. One output gained a
black tail; the other lost its final clip. The agent had measured source clip
durations, but did not verify the assembled timeline invariant.

The general bug is:

```text
segments are valid individually
+ build passes
+ outer duration/count is guessed or duplicated
= valid program, invalid artifact
```

## Verification recipe

1. **Recompute the structural invariant from source data.** For a timeline,
   calculate every segment start and `end = start + duration`, accounting for
   overlaps/transitions. The artifact duration is the maximum end, not the sum
   and not a nearby constant. For batches, compare requested, emitted, and
   deduplicated counts.
2. **Derive outer metadata from the same data model.** Export a helper or
   duration map rather than duplicating magic numbers in composition/root
   declarations.
3. **Run introspection after the last code change.** Examples:
   `remotion compositions`, an ffmpeg concat manifest check, or a batch summary
   that prints expected versus produced counts.
4. **Render current-source boundary and key frames.** At minimum inspect the
   first frame, the last valid frame, and transition/payoff frames. A successful
   render alone does not prove the frame is non-black, non-frozen, or correctly
   framed.
5. **Probe the final container.** With `ffprobe`, verify duration, dimensions,
   frame rate, video/audio codecs, channel count, and non-trivial file size.
   For audio, measure peak/mean level and clipping where relevant.
6. **Sample the whole artifact.** Generate a contact sheet or evenly spaced
   preview frames to catch black gaps, frozen/repeated sections, bad crops, and
   narrative discontinuity that boundary checks miss.
7. **Verify delivery separately.** Re-read uploaded file metadata by ID and
   compare name, parent, MIME type, and size. An upload response is a self-report.
8. **Inspect repository state last.** Run `git status`/`git diff` after checks so
   verification artifacts or late edits are visible. If only documentation
   changed after a full render, state that media was unaffected, but still run a
   current-source compile and boundary-frame render.

## Timeline formula

For sequential clips where clip `i` overlaps the previous clip by `o_i` frames:

```text
from_0 = 0
from_i = end_(i-1) - o_i
end_i  = from_i + duration_i
composition_duration = max(end_i)
```

Keep each used clip duration below its source duration unless intentional frame
holding is part of the design.