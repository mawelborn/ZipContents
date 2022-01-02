import re
from collections import defaultdict
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

import sublime
from sublime_plugin import EventListener

from .viewio import HexViewIO


class ZipFileListener(EventListener):
    _ZIP_SIGNATURES = ("504b 0304", "504b 0506", "504b 00708")
    _OVERLAY_PANEL_ELEMENTS = ("command_palette:input", "goto_anything:input")

    def __init__(self):
        super().__init__()

        if int(sublime.version()) < 4050:
            self._is_overlay_panel = self._is_overlay_panel_heuristic

        self._overlay_panel_open = self._is_overlay_panel(sublime.active_window().active_view())
        self._zip_view_awaiting_panel_close = None

    @classmethod
    def _is_overlay_panel(cls, view):
        return view.element() in cls._OVERLAY_PANEL_ELEMENTS

    @staticmethod
    def _is_overlay_panel_heuristic(view):
        return view.settings().get("is_widget")

    def on_activated(self, view):
        if self._is_overlay_panel(view):
            self._overlay_panel_open = True

    def on_deactivated(self, view):
        if self._is_overlay_panel(view):
            self._overlay_panel_open = False
            self._show_zip_contents_awaiting_panel_close()

    def _show_zip_contents_awaiting_panel_close(self):
        if self._zip_view_awaiting_panel_close:
            zip_contents = ZipContents(self, self._zip_view_awaiting_panel_close)
            self._zip_view_awaiting_panel_close = None
            # A quick panel won't show if an overlay panel is in the process of closing.
            sublime.set_timeout(zip_contents.show, 0)

    def on_load(self, view):
        if view.encoding() == "Hexadecimal" and self._view_starts_with_zip_signature(view):
            if self._overlay_panel_open:
                self._zip_view_awaiting_panel_close = view
            else:
                ZipContents(self, view).show()

    @classmethod
    def _view_starts_with_zip_signature(cls, view):
        signature_region = sublime.Region(0, len(cls._ZIP_SIGNATURES[0]))
        return view.substr(signature_region) in cls._ZIP_SIGNATURES

    def on_close(self, view):
        if view == self._zip_view_awaiting_panel_close:
            self._zip_view_awaiting_panel_close = None


class ZipContents:
    def __init__(self, listener, view):
        self._settings = sublime.load_settings("ZipContents.sublime-settings")
        self._view = view
        self._window = view.window()
        self._file = ZipFile(HexViewIO(view))
        self._contents = self._zip_contents()

    def _zip_contents(self):
        # Remove folder-only entries.
        contents = [file_path for file_path in self._file.namelist() if not file_path.endswith("/")]

        # Remove entries that match file and folder exclude patterns.
        file_exclude_patterns = self._settings.get("file_exclude_patterns")
        folder_exclude_patterns = self._settings.get("folder_exclude_patterns")

        if file_exclude_patterns or folder_exclude_patterns:
            exclude_pattern = self._compile_exclude_pattern(
                file_exclude_patterns, folder_exclude_patterns
            )
            contents = [
                file_path for file_path in contents if not exclude_pattern.search(file_path)
            ]

        return sorted(contents)

    @classmethod
    def _compile_exclude_pattern(cls, file_exclude_patterns, folder_exclude_patterns):
        patterns = []

        if file_exclude_patterns:  # File patterns are followed by end of string.
            patterns += [cls._convert_pattern(pattern) + "$" for pattern in file_exclude_patterns]

        if folder_exclude_patterns:  # Folder patterns are followed by slash.
            patterns += [cls._convert_pattern(pattern) + "/" for pattern in folder_exclude_patterns]

        # Match beginning of string or slash, followed by any pattern.
        return re.compile("(?:^|/)(?:" + "|".join(patterns) + ")")

    @staticmethod
    def _convert_pattern(pattern):
        # Convert "*" and "?" to "[^/]*" and "[^/]" and escape everything else.
        pattern = pattern.replace("*", "__zipcontentsstar__")
        pattern = pattern.replace("?", "__zipcontentsquestion__")
        pattern = re.escape(pattern)
        pattern = pattern.replace("__zipcontentsstar__", "[^/]*")
        pattern = pattern.replace("__zipcontentsquestion__", "[^/]")
        return pattern

    def show(self):
        self._window.show_quick_panel(self._contents, self._extract_file)

    def _extract_file(self, index):
        # Do nothing if no item was selected in the quick panel.
        if index == -1:
            return

        file_path = self._contents[index]
        file_name = file_path.split("/").pop()

        temp_file = NamedTemporaryFile(suffix=file_name)
        temp_file.write(self._file.read(file_path))
        temp_file.flush()

        self._view.close()
        extracted_file_view = self._window.open_file(temp_file.name)

        ExtractedFileListener.set_name_on_load(extracted_file_view, file_name)
        ExtractedFileListener.set_scratch_on_load(extracted_file_view)
        ExtractedFileListener.close_file_on_load(extracted_file_view, temp_file)


class ExtractedFileListener(EventListener):
    _load_callbacks = defaultdict(list)

    @classmethod
    def set_name_on_load(cls, view, name):
        cls._load_callbacks[view.id()].append(lambda: view.set_name(name))

    @classmethod
    def set_scratch_on_load(cls, view):
        cls._load_callbacks[view.id()].append(lambda: view.set_scratch(True))

    @classmethod
    def close_file_on_load(cls, view, file):
        cls._load_callbacks[view.id()].append(lambda: file.close())

    def on_load(self, view):
        view_id = view.id()
        if view_id in self._load_callbacks:
            for callback in self._load_callbacks[view_id]:
                callback()
            del self._load_callbacks[view_id]
