# Security policy

## Supported version

Security fixes are applied to the latest source version.

## Reporting

Do not publish a vulnerability containing a working exploit, private file contents, or secrets in a public issue. Use GitHub's private vulnerability-reporting feature when it is enabled for the repository. Otherwise, open a minimal public issue requesting a private contact channel without including exploit details.

Include the affected version, platform, impact, reproduction conditions, and whether untrusted `.bouncebeat`, MIDI, SoundFont, or media files are involved.

## Scope

Relevant issues include unsafe archive extraction, command injection, arbitrary file overwrite, untrusted media parsing risks, dependency compromise, and unintended disclosure of local paths or project contents.

BounceBeat invokes local FFmpeg and FluidSynth executables. Users should obtain those tools and SoundFonts from trusted sources.
