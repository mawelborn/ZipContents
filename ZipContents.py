from re import compile, escape
from sublime import active_window, load_settings, set_timeout, version, Region
from sublime_plugin import EventListener
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

from .viewio import HexViewIO


ZIP_SIGNATURES = ["504b 0304", "504b 0506", "504b 00708"]

settings = None
zip_contents = None
zip_file = None
zip_window = None


def plugin_loaded():
    global settings
    settings = load_settings("ZipContents.sublime-settings")


class ZipContentsListener(EventListener):
    def __init__(self):
        super().__init__()

        if int(version()) < 4050:
            self.is_quick_panel = self.is_quick_panel_heuristic

        self.quick_panel_open = self.is_quick_panel(active_window().active_view())
        self.pending_zip_view = None

    def is_quick_panel(self, view):
        return view.element() in ("command_palette:input", "goto_anything:input")

    def is_quick_panel_heuristic(self, view):
        return view.settings().get("is_widget")

    def on_activated(self, view):
        if self.is_quick_panel(view):
            self.quick_panel_open = True

    def on_deactivated(self, view):
        if self.is_quick_panel(view):
            self.quick_panel_open = False
            if self.pending_zip_view:
                show_zip_contents(self.pending_zip_view)
                self.pending_zip_view = None

    def on_load(self, view):
        if view.encoding() == "Hexadecimal":
            signature_region = Region(0, len(ZIP_SIGNATURES[0]))
            if view.substr(signature_region) in ZIP_SIGNATURES:
                if self.quick_panel_open:
                    self.pending_zip_view = view
                else:
                    show_zip_contents(view)

    def on_close(self, view):
        if self.pending_zip_view == view:
            self.pending_zip_view = None


def show_zip_contents(view):
    global zip_contents, zip_file, zip_window
    zip_window = view.window()
    zip_file = ZipFile(HexViewIO(view))
    zip_contents = prepare_contents(zip_file.namelist())
    # A quick panel can't be shown on the same frame that another's being deactivated?
    set_timeout(lambda: zip_window.show_quick_panel(zip_contents, extract_file), 1)


def prepare_contents(contents):
    # Remove folder-only entries.
    contents = [file_path for file_path in contents
                if not file_path.endswith("/")]
    # Remove entries that match file and folder exclude patterns.
    file_exclude_patterns = settings.get("file_exclude_patterns")
    folder_exclude_patterns = settings.get("folder_exclude_patterns")
    if file_exclude_patterns or folder_exclude_patterns:
        exclude_patterns = compile_exclude_patterns(file_exclude_patterns,
                                                    folder_exclude_patterns)
        contents = [file_path for file_path in contents
                    if not exclude_patterns.search(file_path)]
    return sorted(contents)


def compile_exclude_patterns(file_exclude_patterns, folder_exclude_patterns):
    patterns = []
    if file_exclude_patterns:  # File patterns are followed by end of string.
        patterns += [convert_pattern(pattern) + "$" for pattern in file_exclude_patterns]
    if folder_exclude_patterns:  # Folder patterns are followed by slash.
        patterns += [convert_pattern(pattern) + "/" for pattern in folder_exclude_patterns]
    # Match beginning of string or slash, followed by any pattern.
    return compile("(?:^|/)(?:" + "|".join(patterns) + ")")


def convert_pattern(pattern):
    # Escape everything but "*" and "?", and convert those to "[^/]*" and "[^/]" respectively.
    pattern = pattern.replace("*", "__zipcontentsstar__")
    pattern = pattern.replace("?", "__zipcontentsquestion__")
    pattern = escape(pattern)
    pattern = pattern.replace("__zipcontentsstar__", "[^/]*")
    pattern = pattern.replace("__zipcontentsquestion__", "[^/]")
    return pattern


def extract_file(index):
    global zip_contents, zip_file, zip_window

    # Do nothing if no item was selected in the quick panel.
    if index == -1:
        zip_window = None
        zip_file = None
        zip_contents = None
        return

    file_path = zip_contents[index]
    file_name = file_path.split("/").pop()
    ntf = NamedTemporaryFile(suffix=file_name)
    ntf.write(zip_file.read(file_path))
    ntf.flush()
    zip_window.run_command("close")
    view = zip_window.open_file(ntf.name)

    zip_window = None
    zip_file = None
    zip_contents = None

    def await_loading():
        if view.is_loading():
            set_timeout(await_loading, 250)
        else:
            view.set_name(file_name)
            view.set_scratch(True)
            ntf.close()

    await_loading()
