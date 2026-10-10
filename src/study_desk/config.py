"""Non-secret provider configuration and local data paths."""
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit


def default_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return base / "StudyDesk"


@dataclass(frozen=True)
class AIConfig:
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"
    secondary_model: str = ""
    secondary_input_price: float = 1.32
    secondary_output_price: float = 3.96
    daily_budget: float = 1.0
    input_price: float = 0.30
    output_price: float = 1.20
    max_output_tokens: int = 2000

    def validate(self):
        parsed = urlsplit(self.base_url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("API 地址必须是没有账号、参数或片段的 HTTPS 地址。")
        if not self.model.strip() or len(self.model) > 100:
            raise ValueError("请填写有效的模型名称。")
        for value in (self.daily_budget, self.input_price, self.output_price,
                      self.secondary_input_price, self.secondary_output_price):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("预算和单价必须是大于 0 的有限数值。")
        if not 128 <= self.max_output_tokens <= 8000:
            raise ValueError("输出长度必须在 128 到 8000 token 之间。")
        return self

    def selected(self, secondary=False):
        from dataclasses import replace
        if secondary:
            if not self.secondary_model.strip():
                raise ValueError("尚未设置第二模型。")
            return replace(self, model=self.secondary_model, input_price=self.secondary_input_price,
                           output_price=self.secondary_output_price)
        return self

    def to_dict(self):
        return asdict(self)
