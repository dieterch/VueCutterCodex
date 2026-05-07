# TODO

## Backend / Runtime

- Clean up CIFS remount logging so normal `umount`-when-not-mounted does not look like a hard failure.
- Differentiate CIFS permission errors, missing credentials, NAS offline, and missing media file paths in backend responses.
- Add one retry/recheck path for transient NAS unavailability before returning media-unavailable errors.
- Make the SMB credentials path configurable in backend code instead of relying on one fixed path.
- Document and preserve the current mixed deployment model: `plex1`/`plex3` via SMB, `plex2` via host-mounted `/mnt/media`.
- Consider a dedicated writable work directory for cut temp files so SMB-backed recordings do not require direct write access in the source folder.
- Validate CIFS-in-container on the production Docker host and stop trying to support it on restricted dev guests.

## Frontend

- Restore usable timeline browsing without reintroducing startup hangs.
- Add cut marker workflow (`t0`, `t1`) and cutlist management to the Nuxt UI.
- Add cut submission dialog and progress polling.
- Add row removal/editing for cutlist entries.
- Add a clear “Retry media” action when the NAS becomes available again.
- Replace the placeholder/minimal layout with a full operator-focused cutting workflow.
