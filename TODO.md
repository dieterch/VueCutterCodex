# TODO

## Backend / Runtime

- Clean up CIFS remount logging so normal `umount`-when-not-mounted does not look like a hard failure.
- Differentiate CIFS permission errors, missing credentials, NAS offline, and missing media file paths in backend responses.
- Add one retry/recheck path for transient NAS unavailability before returning media-unavailable errors.
- Make the SMB credentials path configurable in backend code instead of relying on one fixed path.
- Decide final deployment default: host-mounted media vs SMB-in-container, and document only one primary path.
- Validate CIFS-in-container on the production Docker host and stop trying to support it on restricted dev guests.

## Frontend

- Restore usable timeline browsing without reintroducing startup hangs.
- Add cut marker workflow (`t0`, `t1`) and cutlist management to the Nuxt UI.
- Add cut submission dialog and progress polling.
- Add row removal/editing for cutlist entries.
- Add a clear “Retry media” action when the NAS becomes available again.
- Replace the placeholder/minimal layout with a full operator-focused cutting workflow.
