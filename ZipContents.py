from sublime import set_timeout_async, Region
from sublime_plugin import EventListener
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

from .viewio import HexViewIO


ZIP_SIGNATURES = ["504b 0304", "504b 0506", "504b 00708"]

zip_contents = None
zip_file = None
zip_window = None


class ZipContentsLoadListener(EventListener):
    def on_load_async(self, view):
        if view.encoding() == "Hexadecimal":
            signature_region = Region(0, len(ZIP_SIGNATURES[0]))
            if view.substr(signature_region) in ZIP_SIGNATURES:
                show_zip_contents(view)


def show_zip_contents(view):
    global zip_contents, zip_file, zip_window
    zip_window = view.window()
    zip_file = ZipFile(HexViewIO(view))
    zip_contents = prepare_contents(zip_file.namelist())
    zip_window.show_quick_panel(zip_contents, extract_file)


def prepare_contents(contents):
    return sorted(contents)


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
            set_timeout_async(await_loading, 250)
        else:
            view.set_name(file_name)
            view.set_scratch(True)
            ntf.close()

    await_loading()
