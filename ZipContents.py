import sublime
import sublime_plugin

from os.path import basename
from re import compile
from tempfile import TemporaryDirectory
from zipfile import is_zipfile, ZipFile


class ZipContentsLoadListener(sublime_plugin.EventListener):
    def on_load_async(self, view):
        if is_zipfile(view.file_name()):
            sublime.run_command("zip_contents")


class ZipContentsCommand(sublime_plugin.ApplicationCommand):
    UP_DIRECTORY = "../"

    def __init__(self):
        super().__init__()
        # Temporary directories holding files extracted from zip archives will be automatically
        # deleted when the plugin is unloaded - most importantly when Sublime Text closes.
        self.created_temp_dirs = []

    def run(self):
        self.zip_file_name = sublime.active_window().active_view().file_name()
        with ZipFile(self.zip_file_name) as zip:
            self.zip_contents_filenames = sorted(zip.namelist())
        # This is a stack of directory prefixes for faking hierarchical browsing of the zip file's
        # contents.
        self.dir_prefixes = []
        self.show_items_with_dir_prefix()

    def show_items_with_dir_prefix(self):
        """
        Display a quick panel that lists all the files and directories that are in the current
        directory within the zip file.
        """
        sublime.active_window().show_quick_panel(self.items_with_dir_prefix(), self.select_item)

    def items_with_dir_prefix(self):
        """
        Return a list of items that are directly beneath the top directory prefix in the prefix
        stack. Given 'prefix/' is the current top prefix, return items like:
                 prefix/file
             and prefix/another_file
             and prefix/subdirectory/
         but not prefix/subdirectory/subdir_file
              or prefix/subdirectory/subsubdirectory/
        """
        prefix = self.dir_prefixes[-1] if self.dir_prefixes else ""
        prefix_pattern = compile(prefix + "[^/]+/?$")
        filenames = [filename[len(prefix):]
                     for filename in self.zip_contents_filenames
                     if prefix_pattern.match(filename)]
        if self.dir_prefixes:
            if filenames:
                filenames[0] = self.UP_DIRECTORY
            else:
                filenames.append(self.UP_DIRECTORY)
        return filenames

    def select_item(self, selected_index):
        # Do nothing if no item was selected in the quick panel.
        if selected_index == -1:
            return

        # The quick panel showed the `self.items_with_dir_prefix()` list, so the selected filename
        # is the current directory prefix + the Nth item in that list.
        selected_basename = self.items_with_dir_prefix()[selected_index]
        # If the selected filename is the parent directory, pop the current directory prefix off the
        # stack and reshow the quick panel with the new items that match.
        if selected_basename == self.UP_DIRECTORY:
            self.dir_prefixes.pop()
            self.show_items_with_dir_prefix()
        # If the selected filename is a directory, push it onto the stack of directory prefixes and
        # reshow the quick panel with the new items that match.
        elif selected_basename[-1] == "/":
            self.dir_prefixes.append(selected_basename)
            self.show_items_with_dir_prefix()
        # Otherwise, extract the selected file into a temporary directory and show it in place of
        # the zip archive.
        else:
            dir_prefix = self.dir_prefixes[-1] if self.dir_prefixes else ""
            temp_dir_name = basename(self.zip_file_name) + "__" + dir_prefix
            temp_dir_name = temp_dir_name.replace("/", "_").replace("\\", "_")
            temp_directory = TemporaryDirectory(prefix=temp_dir_name)
            # TemporaryDirectory objects automatically `rm -r` the created filesystem directory when
            # garbage collected. Add it to the list of created_temp_dirs so that it sticks
            # around so long as the plugin is loaded and is automatically cleaned up when the plugin
            # is unloaded. Like when Sublime Text closes.
            self.created_temp_dirs.append(temp_directory)
            temp_file_name = temp_directory.name + "/" + selected_basename
            # Extract the selected file in the zip archive into the temporary directory.
            with open(temp_file_name, "wb") as temp_file, \
                 ZipFile(self.zip_file_name) as zip:
                if self.dir_prefixes:
                    file_in_zip = self.dir_prefixes[-1] + selected_basename
                else:
                    file_in_zip = selected_basename
                temp_file.write(zip.read(file_in_zip))
            # Close the zip file and open the extracted file in its place.
            sublime.active_window().run_command("close")
            sublime.active_window().open_file(temp_file_name)
