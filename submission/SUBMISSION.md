# Submission checklist

- [x] Root `Dockerfile`
- [x] linux/amd64 image verified
- [x] Image size below 8 GB (443,198,577 bytes locally)
- [x] Runs as uid 1000 with read-only root and no network
- [x] Repository data excluded; Docker context is about 43 KB
- [x] MIT license included
- [x] 36/36 official fixtures pass
- [x] 1M official dev answer exact match
- [ ] Generated 20M corpus finishes inside the five-minute practice ceiling (Windows Docker probe exceeded the cap)
- [ ] Public GitHub remote created and pushed (GitHub authentication required)
- [ ] Commit submitted on track page (Buildathon authentication required)
- [ ] Official score/rank/feedback recorded

Suggested repository: `builders-shopping-sessions`

Implementation baseline before the spill hardening/report update: `891fa4f2851c5009002cda0208a81d61118efdb5`.

Use `git rev-parse HEAD` for the final SHA to submit after any documentation update.

Submission URL: https://www.joinbuilders.org/buildathon/tracks/shopping-sessions
