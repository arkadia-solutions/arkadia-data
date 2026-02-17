
import sys
import argparse
import arkadia.cli as cli
from arkadia.cli.colors import C
from arkadia.cli.print_options import print_options
from arkadia.cli.print_usage import print_usage
import arkadia.cli.aid.benchmark as benchmark
from arkadia.cli.aid.meta import MET_INFO, VERSION, TOOL_NAME, TOOL_CMD, DESCRIPTION
import arkadia.cli.aid.encode as encode
import arkadia.cli.aid.decode as decode

def show_main_help():
    cli.print_banner(
        tool_name=TOOL_NAME, 
        version=VERSION,
        color=C.RED,
        description=DESCRIPTION,
        metadata=MET_INFO
    )
    cli.print_usage(TOOL_CMD, "<command> [flags]", "")


    commands = [
        {"flags": "enc", "desc": "[ENCODE] Convert JSON/YAML/TOON to AI.Data format"},
        {"flags": "dec", "desc": "[DECODE] Parse AI.Data format back to JSON"},
        {"flags": "benchmark", "desc": "[BENCHMARK] Run performance and token usage tests"},
        {"flags": "ai-benchmark", "desc":  "[AI] Run AI understanding tests"},
    ]
    cli.print_options("Commands", commands)

    flags = [
        {"flags": "-h, --help", "desc": "Show this help message"},
        {"flags": "-v, --version", "desc": "Show version info"}
    ]
    cli.print_options("Global Options", flags)

def main():
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("command", nargs="?", default="help", 
                        choices=["enc", "dec", "benchmark", "ai-benchmark",  "help"],
                        help="Command to execute")
    
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-v", "--version", action="store_true")

    args, rest = parser.parse_known_args()

    if args.version:
        print(f"{TOOL_NAME} v{VERSION}")
        return

    if ( (args.help and not rest and not args.command ) or args.command == "help"):
        show_main_help()
        return

    try:
        if args.command == "enc":
            if args.help:
                encode.show_encode_help()
                return

            enc_parser = argparse.ArgumentParser(add_help=False)
            encode.register_arguments(enc_parser)
            enc_args = enc_parser.parse_args(rest)
            encode.run(enc_args)
            
        elif args.command == "dec":
            if args.help:
                decode.show_decode_help()
                return
            
            dec_parser = argparse.ArgumentParser(add_help=False)
            decode.register_arguments(dec_parser)
            dec_args = dec_parser.parse_args(rest)
            decode.run(dec_args)


        elif args.command == "benchmark":
            if args.help:
                benchmark.show_benchmark_help()
                return
            
            ben_parser = argparse.ArgumentParser(add_help=False)
            benchmark.register_arguments(ben_parser)
            ben_args = ben_parser.parse_args(rest)
            benchmark.run(ben_args)

        elif args.command == "perf":
            pass
            # benchmark.run_performance_mode()
            
        elif args.command == "ai":
            pass
            # benchmark.run_ai_test()
            
            
        else:
            show_main_help()

    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Operation cancelled by user.{C.RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{C.RED}Fatal Error:{C.RESET} {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()