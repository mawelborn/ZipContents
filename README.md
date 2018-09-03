# ZipContents

A Sublime Text 3 plugin for browsing and viewing the contents of opened zip files. Useful for
quickly referencing archived files in completed projects.


## Installation

Put `ZipContents.sublime-package` in `<data_path>/Installed Packages/`.


## Usage

Open a zip file (or other filetype based on zip) with Sublime Text. A quick panel will display the
contents of the root of the zip file. Select a directory to show its contents. Select `../` to go up
a directory. Select a file to extract it and open it in place of the zip file.

Zip file contents opened with this plugin are extracted to temporary directories that are
automatically cleaned up when Sublime Text is closed.
