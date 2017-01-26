"""
    Name:   main-test.py
    Author: Francis T
    Desc:   Executes functional tests for the different parts of the system
"""

import test.test__request_handler as trh

def main():
    # Run the Request Handler test suite
    test_req_handler = trh.TestSuite()
    test_req_handler.run()
    
    return

if __name__ == "__main__":
    main()

