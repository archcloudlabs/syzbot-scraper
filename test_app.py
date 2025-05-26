import os
import pytest
import responses
from bs4 import BeautifulSoup
from app import (
    fetch_url,
    sanitize_directory_name,
    create_output_directory,
    extract_asset_links,
    save_asset,
    download_single_asset,
    extract_bug_links,
    BASE_URL
)

@pytest.fixture
def sample_html():
    return """
    <html>
        <head><title>Test Bug Title</title></head>
        <body>
            <tbody>
                <tr></tr>
                <tr>
                    <td class="assets">
                        <a href="/download?tag=test.raw">Raw File</a>
                        <a href="/download?tag=test.txt">Text File</a>
                    </td>
                    <td class="repro">
                        <a href="/repro?tag=repro.c">Repro File</a>
                    </td>
                    <td class="title">
                        <a href="/bug?id=123">Bug Title</a>
                    </td>
                </tr>
            </tbody>
        </body>
    </html>
    """

@pytest.fixture
def sample_soup(sample_html):
    return BeautifulSoup(sample_html, 'html.parser')

def test_sanitize_directory_name():
    """Test directory name sanitization"""
    test_cases = [
        ("Hello World", "Hello_World"),
        ("test/path", "test_path"),
        ("name:with:colons", "name_with_colons"),
        ("mixed-with-hyphens", "mixed_with_hyphens"),
        ("multiple   spaces", "multiple___spaces"),
    ]
    
    for input_str, expected in test_cases:
        assert sanitize_directory_name(input_str) == expected

def test_create_output_directory(tmp_path):
    """Test output directory creation"""
    test_dir = "test_dir"
    expected_path = os.path.join(tmp_path, test_dir)
    
    # Test with tmp_path as current directory
    os.chdir(tmp_path)
    result_path = create_output_directory(test_dir)
    
    assert os.path.exists(expected_path)
    assert os.path.isdir(expected_path)
    assert result_path == f"./output/{test_dir}"

    # Test creating nested directory
    nested_dir = "parent/child"
    create_output_directory(nested_dir)
    assert os.path.exists(os.path.join(tmp_path, "output", "parent", "child"))

@responses.activate
def test_fetch_url():
    """Test URL fetching with mocked responses"""
    test_url = "https://test.com"
    
    # Test successful response
    responses.add(responses.GET, test_url, 
                 body="test content", 
                 status=200)
    response = fetch_url(test_url)
    assert response is not None
    assert response.text == "test content"
    
    # Test timeout
    responses.replace(responses.GET, test_url,
                     body=responses.ConnectionError())
    response = fetch_url(test_url)
    assert response is None

def test_extract_asset_links(sample_soup):
    """Test extraction of asset links from HTML"""
    links = extract_asset_links(sample_soup)
    
    assert len(links) == 3
    assert "/download?tag=test.raw" in links
    assert "/download?tag=test.txt" in links
    assert f"{BASE_URL}/repro?tag=repro.c" in links

def test_save_asset(tmp_path):
    """Test saving assets to disk"""
    output_dir = str(tmp_path)
    
    # Test binary content
    binary_content = b"binary data"
    assert save_asset(output_dir, "test.raw", binary_content, is_binary=True)
    with open(os.path.join(output_dir, "test.raw"), "rb") as f:
        assert f.read() == binary_content
    
    # Test text content
    text_content = b"text data"
    assert save_asset(output_dir, "test.txt", text_content, is_binary=False)
    with open(os.path.join(output_dir, "test.txt"), "r") as f:
        assert f.read() == "text data"

def test_extract_bug_links(sample_soup):
    """Test extraction of bug links and data"""
    rows, links = extract_bug_links(sample_soup)
    
    assert len(rows) == 1
    assert len(links) == 1
    assert links[0] == f"{BASE_URL}/bug?id=123"

@responses.activate
def test_download_single_asset(tmp_path):
    """Test downloading a single asset"""
    os.chdir(tmp_path)
    os.makedirs("output")
    
    test_url = "https://test.com/download?tag=test.txt"
    test_content = "test content"
    
    # Test successful download
    responses.add(responses.GET, test_url,
                 body=test_content,
                 status=200)
    
    assert download_single_asset(test_url, str(tmp_path))
    assert os.path.exists(os.path.join(tmp_path, "test.txt"))
    
    # Test failed download
    responses.replace(responses.GET, test_url,
                     body=responses.ConnectionError())
    assert not download_single_asset(test_url, str(tmp_path)) 