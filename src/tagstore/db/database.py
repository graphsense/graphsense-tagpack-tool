from sqlmodel import SQLModel, create_engine


def get_db_engine(db_url):
    return create_engine(db_url)


def create_db_and_tables(engine):
    SQLModel.metadata.create_all(engine)
