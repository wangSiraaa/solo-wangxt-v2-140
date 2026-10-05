"""SQLAlchemy 模型：参考物相条目与其峰表。仅存开放/自制示例数据。"""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ReferencePattern(Base):
    __tablename__ = "reference_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    formula: Mapped[str] = mapped_column(String(100), default="")
    source: Mapped[str] = mapped_column(String(300), default="self-made teaching example")
    note: Mapped[str] = mapped_column(Text, default="")

    peaks: Mapped[list["ReferencePeak"]] = relationship(
        back_populates="pattern", cascade="all, delete-orphan",
        order_by="ReferencePeak.d_angstrom.desc()")


class ReferencePeak(Base):
    __tablename__ = "reference_peaks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern_id: Mapped[int] = mapped_column(ForeignKey("reference_patterns.id"))
    d_angstrom: Mapped[float] = mapped_column(Float)
    intensity_rel: Mapped[float] = mapped_column(Float)  # 0-100

    pattern: Mapped[ReferencePattern] = relationship(back_populates="peaks")
