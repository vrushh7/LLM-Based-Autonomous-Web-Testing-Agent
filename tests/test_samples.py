"""
Sample Test Cases
Demonstrates various testing scenarios that can be executed with the AI Testing Agent
"""

# Sample Test Instructions
# These can be used directly in the UI or via API

SAMPLE_TESTS = [
    # Basic Navigation Tests
    {
        "name": "Simple Navigation Test",
        "instruction": "Open example.com and verify the page loads",
        "expected_outcome": "Page should load successfully with visible content"
    },
    
    {
        "name": "Title Verification Test",
        "instruction": "Navigate to example.com and verify the page title contains 'Example'",
        "expected_outcome": "Page title should contain the word 'Example'"
    },
    
    # Search Functionality Tests
    {
        "name": "Google Search Test",
        "instruction": "Go to Google, search for 'Python testing', and verify search results appear",
        "expected_outcome": "Search results should be visible after search"
    },
    
    {
        "name": "DuckDuckGo Search Test",
        "instruction": "Open DuckDuckGo, type 'artificial intelligence' in the search box, click search, and verify results are displayed",
        "expected_outcome": "Search results page should display with relevant results"
    },
    
    # Form Interaction Tests
    {
        "name": "GitHub Sign In Navigation",
        "instruction": "Navigate to GitHub, click on Sign in, and verify the login form is visible",
        "expected_outcome": "Login form with username and password fields should appear"
    },
    
    {
        "name": "Contact Form Test",
        "instruction": "Open example.com, find the contact link, click it, and verify a contact form appears",
        "expected_outcome": "Contact form should be visible with input fields"
    },
    
    # Multi-step Tests
    {
        "name": "Wikipedia Navigation Test",
        "instruction": "Go to Wikipedia, click on the search box, enter 'Artificial Intelligence', press enter, and verify the AI article loads",
        "expected_outcome": "AI article page should load with content visible"
    },
    
    {
        "name": "Documentation Navigation",
        "instruction": "Navigate to Python.org, click on Documentation, click on Tutorial, and verify the tutorial page loads",
        "expected_outcome": "Python tutorial page should be visible"
    },
    
    # Element Visibility Tests
    {
        "name": "Header Visibility Test",
        "instruction": "Open GitHub.com and verify the main navigation header is visible",
        "expected_outcome": "Navigation header should be present at top of page"
    },
    
    {
        "name": "Footer Verification",
        "instruction": "Navigate to example.com, scroll to bottom, and verify footer is visible",
        "expected_outcome": "Footer element should be visible"
    },
    
    # URL Verification Tests
    {
        "name": "Redirect Verification",
        "instruction": "Navigate to http://example.com and verify the URL contains 'example'",
        "expected_outcome": "URL should contain 'example' after navigation"
    },
    
    # Negative Tests
    {
        "name": "404 Error Page Test",
        "instruction": "Navigate to example.com/nonexistent-page and verify error page appears",
        "expected_outcome": "Error page or 404 message should be displayed"
    },
    
    # Real-world Scenarios
    {
        "name": "E-commerce Product Search",
        "instruction": "Open Amazon.com, search for 'laptop', and verify product listings appear",
        "expected_outcome": "Product listing page should show laptop results"
    },
    
    {
        "name": "News Website Test",
        "instruction": "Navigate to BBC.com and verify headlines are visible on the homepage",
        "expected_outcome": "News headlines should be displayed on the page"
    },
    
    {
        "name": "Social Media Login Page",
        "instruction": "Go to Twitter.com, click Sign in, and verify login form is displayed",
        "expected_outcome": "Login form should appear with username/password fields"
    },
    
    # Advanced Tests
    {
        "name": "Video Platform Test",
        "instruction": "Navigate to YouTube.com, search for 'Python tutorial', and verify video results appear",
        "expected_outcome": "Video search results should be displayed"
    },
    
    {
        "name": "Repository Navigation",
        "instruction": "Go to GitHub, search for 'python', click on the first result, and verify repository page loads",
        "expected_outcome": "Repository page should display with code and README"
    },
    
    # Simple Assertion Tests
    {
        "name": "Logo Visibility Test",
        "instruction": "Open Google.com and verify the Google logo is visible",
        "expected_outcome": "Google logo should be visible on homepage"
    },
    
    {
        "name": "Search Box Test",
        "instruction": "Navigate to DuckDuckGo and verify search input field is present",
        "expected_outcome": "Search input field should be visible and interactive"
    },
    
    # Time-based Tests
    {
        "name": "Page Load Test",
        "instruction": "Open example.com, wait 2 seconds, and verify page content is loaded",
        "expected_outcome": "Page content should be fully loaded after wait"
    }
]


def print_sample_tests():
    """Print all sample tests in a readable format"""
    print("=" * 80)
    print("AI TESTING AGENT - SAMPLE TEST CASES")
    print("=" * 80)
    print()
    
    for i, test in enumerate(SAMPLE_TESTS, 1):
        print(f"{i}. {test['name']}")
        print(f"   Instruction: {test['instruction']}")
        print(f"   Expected: {test['expected_outcome']}")
        print()


def get_test_by_name(name: str):
    """Get a specific test by name"""
    for test in SAMPLE_TESTS:
        if test['name'].lower() == name.lower():
            return test
    return None


def get_random_test():
    """Get a random test case"""
    import random
    return random.choice(SAMPLE_TESTS)


if __name__ == "__main__":
    print_sample_tests()
    
    print("\nTo use these tests:")
    print("1. Start the backend server: python backend/main.py")
    print("2. Open the frontend: http://localhost:8080")
    print("3. Copy any instruction above into the input field")
    print("4. Click 'Run Test'")
    print()
    print("OR use the API directly:")
    print('curl -X POST http://localhost:8000/api/test \\')
    print('  -H "Content-Type: application/json" \\')
    print(f'  -d \'{{"instruction": "{SAMPLE_TESTS[0]["instruction"]}"}}\'')
