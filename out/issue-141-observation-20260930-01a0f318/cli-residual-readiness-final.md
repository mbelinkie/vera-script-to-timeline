Added the two requested ignored files under [out/issue-141-observation-20260930-01a0f318](REPOSITORY/out/issue-141-observation-20260930-01a0f318):

- `independent-residual-sequence.py` runs the existing fake R2-residual sequence and checks that a wrong selected ID refuses before Razor.
- `residual-local-readiness.json` records the verified absolute helper paths and hashes, the fake-check command, and the fresh post-Graphic checkpoint prerequisite. Native dispatch remains unauthorized.

Verified with:

```sh
python3 out/issue-141-observation-20260930-01a0f318/independent-residual-sequence.py --check
```

The check passed. Both files remain ignored under `out/`.