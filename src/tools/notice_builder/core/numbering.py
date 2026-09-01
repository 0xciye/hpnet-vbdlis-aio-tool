import re
from datetime import date
from .models import UserError


def parse_numbers(text):
    if not text.strip():
        raise UserError("Danh sách số thông báo đang trống.")
    numbers, seen = [], set()
    for segment in text.split(","):
        match = re.fullmatch(r"\s*([0-9]+)\s*(?:-\s*([0-9]+)\s*)?", segment)
        if not match:
            raise UserError(f"Danh sách số không hợp lệ tại «{segment}». Ví dụ đúng: 1,3,5-13.")
        start = int(match[1]); end = int(match[2]) if match[2] else start
        if start <= 0 or end < start or end > 2147483647:
            raise UserError("Số thông báo phải dương; khoảng số phải tăng dần và không vượt 2147483647.")
        if end - start + 1 + len(numbers) > 100000:
            raise UserError("Danh sách số quá dài (tối đa 100.000 số).")
        for number in range(start, end + 1):
            if number in seen:
                raise UserError(f"Số {number} bị lặp. Hãy sửa danh sách; ứng dụng không tự bỏ số trùng.")
            seen.add(number); numbers.append(number)
    return numbers


def compile_number_dates(config):
    """Validate optional number/date groups and return the date for each explicit number."""
    rules = config.number_date_rules or []
    if config.number_mode != "list" or not rules:
        return {}
    explicit = set(parse_numbers(config.number_list))
    compiled = {}
    for index, rule in enumerate(rules, 1):
        if not isinstance(rule, dict):
            raise UserError(f"Nhóm ngày {index} không đúng định dạng cấu hình.")
        specification = str(rule.get("numbers", "")).strip()
        raw_date = str(rule.get("date", "")).strip()
        if not specification or not raw_date:
            raise UserError(f"Nhóm ngày {index} cần nhập đủ số thông báo và ngày áp dụng.")
        try:
            numbers = parse_numbers(specification)
        except UserError as exc:
            raise UserError(f"Nhóm ngày {index}: {exc}") from None
        try:
            rule_date = date.fromisoformat(raw_date)
        except ValueError:
            raise UserError(f"Ngày của nhóm {index} không hợp lệ.") from None
        outside = [number for number in numbers if number not in explicit]
        if outside:
            shown = ", ".join(map(str, outside[:5]))
            if len(outside) > 5:
                shown += ", ..."
            raise UserError(f"Nhóm ngày {index} có số {shown} không nằm trong Danh sách số thông báo.")
        overlap = [number for number in numbers if number in compiled]
        if overlap:
            raise UserError(f"Số {overlap[0]} đang thuộc nhiều nhóm ngày. Mỗi số chỉ được có một ngày thông báo.")
        compiled.update({number: rule_date for number in numbers})
    return compiled


class NumberPool:
    def __init__(self, mode="start", start=1, text="", continuation=None):
        if mode not in {"start", "list"}:
            raise UserError("Chế độ cấp số không hợp lệ.")
        self.explicit = parse_numbers(text) if mode == "list" else []
        self.tail = start if mode == "start" else continuation
        if self.tail is not None and (not isinstance(self.tail, int) or not 1 <= self.tail <= 2147483647):
            raise UserError("Số bắt đầu phải là số nguyên dương.")
        if mode == "list" and self.tail is not None and self.tail <= max(self.explicit):
            raise UserError("Số tiếp nối phải lớn hơn mọi số trong danh sách để không cấp trùng.")
        self.index = 0
        self.number_dates = {}

    @classmethod
    def from_config(cls, config):
        pool = cls(config.number_mode, config.start_number, config.number_list, config.continue_number)
        pool.number_dates = compile_number_dates(config)
        return pool

    def date_for(self, number, default):
        return self.number_dates.get(number, default)

    def peek(self):
        if self.index < len(self.explicit):
            return self.explicit[self.index]
        if self.tail is None:
            return None
        number = self.tail + self.index - len(self.explicit)
        return number if number <= 2147483647 else None

    def commit(self, number):
        if number is None or number != self.peek():
            raise UserError("Không thể ghi nhận số thông báo khác số đang chờ.")
        self.index += 1

    def preview_number(self, offset):
        from copy import deepcopy
        copy = deepcopy(self)
        for _ in range(offset):
            candidate = copy.peek()
            if candidate is None:
                return None
            copy.commit(candidate)
        return copy.peek()
