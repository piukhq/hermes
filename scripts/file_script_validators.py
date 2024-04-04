from csv import DictReader
from io import TextIOWrapper
from typing import TYPE_CHECKING

from django.forms import ValidationError

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile
    from django.db.models.fields.files import FieldFile

    from scripts.corrections.file_scripts import ColumnTypeSchema


def _validate_file_content(
    input_file: "UploadedFile | FieldFile", column_value_map: "dict[str, ColumnTypeSchema]"
) -> None:
    text_input = TextIOWrapper(input_file, encoding="utf-8")
    reader = DictReader(text_input)

    if not set(column_value_map).issubset(set(reader.fieldnames)):
        raise ValidationError(
            "The file must contain columns %(expected)s, found instead %(found)s",
            params={
                "expected": list(column_value_map),
                "found": reader.fieldnames,
            },
            code="invalid_column_name",
        )

    for row_n, row in enumerate(reader, start=1):
        if row_n > 2000:
            raise ValidationError(
                "This file is too large, please split it into smaller files (rows limit: 2000)",
                code="invalid_row_count",
            )

        for column, column_type in column_value_map.items():
            if not column_type.is_valid(row[column]):
                raise ValidationError(
                    "values in the '%(column_name)s' column must be or type '%(column_type)s'",
                    params={
                        "column_name": column,
                        "column_type": column_type.name,
                    },
                    code="invalid_column_type",
                )

    # Need to detach TextIOWrapper from the wrapped input_file or DictReader
    # will automatically close it when it goes out of scope
    text_input.detach()


def input_file_validation(
    input_file: "UploadedFile | FieldFile", column_value_map: "dict[str, ColumnTypeSchema]"
) -> None:
    try:
        *_, ext = input_file.name.rsplit(".", 1)
        if ext.lower() != "csv":
            raise ValueError

        if input_file.closed:
            with input_file.open("rb") as stream:
                _validate_file_content(stream, column_value_map)
        else:
            # If this is an "UplodedFile" object, it is already open as it is just a django wrapper around a
            # BytesIO object.
            # Opening it with a context manager will cause it to be automatically closed causing an error when django
            # tries to save it.
            _validate_file_content(input_file, column_value_map)

    except ValidationError:
        raise
    except Exception:
        raise ValidationError(
            "invalid file format, please make sure the file is a CSV file with a column named 'ids'",
            code="invalid_file_format",
        ) from None
