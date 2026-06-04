import os

from harbinger import task


@task
def hello() -> None:
    print("Hello!")


@task
def listdir() -> None:
    print(*os.listdir())
