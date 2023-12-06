def function_add_or_update(*args):
    if not args:
        print(
            "Please provide a subcommand. The only available subcommands is 'add' currently, which will both add and update."
        )
        exit(1)
    print(args)
