import logging

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("PulseAlpha Worker starting — LangGraph supervisor wired in Phase 3")


if __name__ == "__main__":
    main()
