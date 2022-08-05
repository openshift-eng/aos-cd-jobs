class VerificationError(ValueError):
    pass


class GithubApiException(Exception):
    """GiHub API exceptions"""
    pass


class ReleaseConfigUpdateError(Exception):
    """Exception raised when there's an error while updating releases.yml file"""
